"""Extract, override, sign, verify and repack an IPA."""

import logging
import os
import re
import shutil
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from wispsign.certs.profile import parse_profile
from wispsign.certs.store import CertStore
from wispsign.errors import WispError
from wispsign.paths import make_work_dir
from wispsign.signing.entitlements import verify_entitlements
from wispsign.signing.ipa import long_path, pack_ipa, safe_extract
from wispsign.signing.plist_edit import apply_overrides, read_info
from wispsign.signing.verify import verify_bundle
from wispsign.signing.zsign import ZsignRunner, zsign_path

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_NAME = 100
_FALLBACK_NAME = "app"
_MAX_BAD_REPORTED = 20
_PACKED = "signed.ipa"
# Antivirus scanners briefly lock freshly written files; retry a few times.
_CLEANUP_ATTEMPTS = 3
_CLEANUP_DELAY_S = 0.25

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignRequest:
    ipa: Path
    cert_id: str
    name: str | None = None
    bundle_id: str | None = None
    icon_png: bytes | None = None


def _safe_file_name(name: str) -> str:
    cleaned = _UNSAFE_CHARS.sub("_", name)[:_MAX_NAME].strip().rstrip(".")
    return cleaned or _FALLBACK_NAME


def _sign_in(
    work: Path,
    req: SignRequest,
    certs: CertStore,
    runner: ZsignRunner,
    on_step: Callable[[str], None],
) -> tuple[Path, Path]:
    """Run every step inside ``work``; return the signed app and packed IPA there."""
    p12, profile, password = certs.materialize(req.cert_id)
    on_step("extract")
    app = safe_extract(req.ipa, work)
    apply_overrides(app, req.name, req.bundle_id, req.icon_png)
    on_step("sign")
    runner.sign(app, p12, profile, password)
    on_step("verify")
    result = verify_bundle(app)
    if not result.ok:  # local check: the install is never attempted
        raise WispError("error.verify_failed", bad=list(result.bad[:_MAX_BAD_REPORTED]))
    verify_entitlements(app, parse_profile(profile.read_bytes()))
    on_step("pack")
    return app, pack_ipa(app, work / _PACKED)


def sign_ipa(
    req: SignRequest,
    certs: CertStore,
    out_dir: Path,
    on_step: Callable[[str], None],
    runner: ZsignRunner | None = None,
    work_base: Path | None = None,
) -> Path:
    """Sign ``req.ipa`` and return ``out_dir/<name>-signed.ipa``.

    The work dir is short (zsign.exe mis-hashes files past MAX_PATH) and is
    always removed, so a failed run leaves no partial IPA behind.
    """
    runner = runner if runner is not None else ZsignRunner(zsign_path())
    work = make_work_dir(work_base)
    try:
        app, packed = _sign_in(work, req, certs, runner, on_step)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{_safe_file_name(read_info(app).name)}-signed.ipa"
        try:
            os.replace(packed, out)
        except OSError:  # e.g. work dir and out_dir on different drives
            shutil.move(packed, out)
        return out
    finally:
        _remove_work_dir(work)


def _clear_readonly_and_retry(func: Callable, path: str, exc: BaseException) -> None:
    if isinstance(exc, FileNotFoundError):
        return
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_work_dir(work: Path) -> None:
    """Delete the work dir; never raises, so the original error is kept."""
    target = long_path(work)
    for attempt in range(1, _CLEANUP_ATTEMPTS + 1):
        try:
            shutil.rmtree(target, onexc=_clear_readonly_and_retry)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if attempt == _CLEANUP_ATTEMPTS:
                _log.warning("could not remove work dir %s: %s", work, exc)
                return
            time.sleep(_CLEANUP_DELAY_S)
