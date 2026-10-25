import logging
import os
import stat
import sys
from pathlib import Path

import pytest
from appgen import APP_NAME, make_app, make_ipa
from certgen import make_pair

from wispsign.certs.store import CertStore
from wispsign.errors import ERROR_CODES, WispError
from wispsign.paths import make_work_dir
from wispsign.signing import pipeline
from wispsign.signing.ipa import safe_extract
from wispsign.signing.pipeline import SignRequest, sign_ipa
from wispsign.signing.plist_edit import read_info
from wispsign.signing.verify import verify_bundle
from wispsign.signing.zsign import ZsignRunner, zsign_path

MAX_PATH = 260
_FITS_TOTAL = 250  # deep file path length under the default work dir
_LONG_TOTAL = 320  # deep file path length under a deliberately long work dir
_MIN_DEEP_REL = 120
# make_work_dir names are 4 characters; the IPA unpacks to Payload/Test.app.
_WORK_APP_TAIL = ("xxxx", "Payload", f"{APP_NAME}.app")


class _FailingRunner(ZsignRunner):
    def __init__(self) -> None:
        super().__init__(zsign_path())

    def sign(self, app_dir, p12, profile, password):
        raise WispError("error.sign_failed", detail="boom")


class _TamperingRunner(ZsignRunner):
    """Signs for real, then changes a sealed file so verification must fail."""

    def __init__(self) -> None:
        super().__init__(zsign_path())

    def sign(self, app_dir, p12, profile, password):
        super().sign(app_dir, p12, profile, password)
        (app_dir / "res.txt").write_bytes(b"tampered")


class _EntitlementTamperingRunner(ZsignRunner):
    def __init__(self, before: bytes, after: bytes) -> None:
        super().__init__(zsign_path())
        self.before = before
        self.after = after

    def sign(self, app_dir, p12, profile, password):
        super().sign(app_dir, p12, profile, password)
        executable = app_dir / APP_NAME
        data = executable.read_bytes()
        assert self.before in data and len(self.before) == len(self.after)
        executable.write_bytes(data.replace(self.before, self.after))


class _InterruptingRunner(ZsignRunner):
    def __init__(self) -> None:
        super().__init__(zsign_path())

    def sign(self, app_dir, p12, profile, password):
        raise KeyboardInterrupt


class _ReadOnlyFailingRunner(ZsignRunner):
    """Leaves a read-only file behind, as some IPAs do, then fails."""

    def __init__(self) -> None:
        super().__init__(zsign_path())

    def sign(self, app_dir, p12, profile, password):
        os.chmod(app_dir / "res.txt", stat.S_IREAD)
        raise WispError("error.sign_failed", detail="boom")


def _run(tmp_paths, tmp_path, cert_id, runner, work):
    return sign_ipa(
        SignRequest(make_ipa(tmp_path), cert_id),
        CertStore(tmp_paths),
        tmp_path / "out",
        lambda s: None,
        runner,
        work,
    )


def test_error_codes_registered():
    for code in ("error.sign_failed", "error.verify_failed", "error.zsign_missing"):
        assert code in ERROR_CODES


def test_sign_pipeline_happy(tmp_paths, tmp_path, fake_cert):
    steps = []
    out = sign_ipa(
        SignRequest(make_ipa(tmp_path), fake_cert.id),
        CertStore(tmp_paths),
        tmp_path / "out",
        steps.append,
    )
    assert steps == ["extract", "sign", "verify", "pack"] and out.exists()
    assert out == tmp_path / "out" / "Test-signed.ipa"
    app = safe_extract(out, make_work_dir(tmp_path / "chk"))
    assert verify_bundle(app).ok
    assert read_info(app).bundle_id == "com.test.app"


def test_sign_applies_overrides_and_sanitizes_name(tmp_paths, tmp_path, fake_cert):
    req = SignRequest(make_ipa(tmp_path), fake_cert.id, "My:App/<1>?", "com.test.new")
    work = tmp_path / "work"
    out = sign_ipa(
        req, CertStore(tmp_paths), tmp_path / "out", lambda s: None, None, work
    )
    assert out.name == "My_App__1__-signed.ipa"
    app = safe_extract(out, make_work_dir(tmp_path / "chk"))
    info = read_info(app)
    assert info.name == "My:App/<1>?" and info.bundle_id == "com.test.new"
    assert verify_bundle(app).ok
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    "before,after",
    [
        (b"production", b"invalid___"),
        (b"aps-environment", b"aps-environmenx"),
        (b"TEAM123456.com.test.app", b"TEAM123456.com.fake.app"),
    ],
)
def test_sign_rejects_changed_signed_entitlements(tmp_paths, tmp_path, before, after):
    p12, profile, password = make_pair(app_id="com.test.app", push=True)
    certs = CertStore(tmp_paths)
    cert = certs.import_pair(p12, profile, password, "Push")
    work = tmp_path / "work"
    steps = []
    with pytest.raises(WispError) as err:
        sign_ipa(
            SignRequest(make_ipa(tmp_path), cert.id),
            certs,
            tmp_path / "out",
            steps.append,
            _EntitlementTamperingRunner(before, after),
            work,
        )
    assert err.value.code == "error.entitlements_invalid"
    assert "pack" not in steps and not (tmp_path / "out").exists()
    assert list(work.iterdir()) == []


def test_sign_keeps_push_entitlements_in_the_packed_ipa(tmp_paths, tmp_path):
    p12, profile, password = make_pair(app_id="com.test.app", push=True)
    certs = CertStore(tmp_paths)
    cert = certs.import_pair(p12, profile, password, "Push")
    out = sign_ipa(
        SignRequest(make_ipa(tmp_path), cert.id),
        certs,
        tmp_path / "out",
        lambda _: None,
    )
    app = safe_extract(out, tmp_path / "check")
    from wispsign.signing.entitlements import read_entitlements

    assert read_entitlements(app / APP_NAME)[0]["aps-environment"] == "production"
    assert (
        read_entitlements(app / APP_NAME)[0]["application-identifier"]
        == "TEAM123456.com.test.app"
    )


def _work_app_len(work_base: Path) -> int:
    """Length of ``<work_base>/<4-char work dir>/Payload/Test.app``."""
    return len(os.path.join(os.path.abspath(work_base), *_WORK_APP_TAIL))


def _deep_rel_len() -> int:
    """Inner deep-file length that just fits MAX_PATH under the default work dir."""
    default_base = Path(os.environ["LOCALAPPDATA"]) / "WS"
    rel_len = _FITS_TOTAL - _work_app_len(default_base) - 1
    assert rel_len >= _MIN_DEEP_REL, "LOCALAPPDATA too long for this test"
    return rel_len


def _deep_ipa(tmp_path: Path, rel_len: int) -> Path:
    """IPA whose deep file is ``rel_len`` chars inside the app and > MAX_PATH here."""
    src_app = os.path.abspath(tmp_path / "src" / f"{APP_NAME}.app")
    deep_path_len = len(src_app) + 1 + rel_len
    assert deep_path_len > MAX_PATH, "tmp_path too short to build a long-path IPA"
    return make_ipa(tmp_path, deep_path_len=deep_path_len)


def _deep_rel(app: Path) -> str:
    (deep,) = list(app.rglob("deep.bin"))
    return os.path.relpath(deep, app)


def test_sign_deep_paths_verifies(tmp_paths, tmp_path, fake_cert):
    rel_len = _deep_rel_len()
    ipa = _deep_ipa(tmp_path, rel_len)  # exceeds 260 if unpacked under a long dir
    out = sign_ipa(
        SignRequest(ipa, fake_cert.id),
        CertStore(tmp_paths),
        tmp_path / "out",
        lambda s: None,
    )
    app = safe_extract(out, make_work_dir(tmp_path / "chk"))
    r = verify_bundle(app)
    assert r.ok and r.bundles_checked == 2
    rel = _deep_rel(app)
    assert len(rel) >= rel_len
    default_base = Path(os.environ["LOCALAPPDATA"]) / "WS"
    assert _work_app_len(default_base) + 1 + len(rel) < MAX_PATH


def test_sign_deep_paths_under_long_work_dir_is_rejected(
    tmp_paths, tmp_path, fake_cert
):
    rel_len = _deep_rel_len()
    ipa = _deep_ipa(tmp_path, rel_len)
    padding = _LONG_TOTAL - (_work_app_len(tmp_path / "w") + 1 + rel_len)
    work = tmp_path / ("w" * (1 + max(0, padding)))
    assert _work_app_len(work) + 1 + rel_len >= _LONG_TOTAL
    with pytest.raises(WispError) as err:
        sign_ipa(
            SignRequest(ipa, fake_cert.id),
            CertStore(tmp_paths),
            tmp_path / "out",
            lambda s: None,
            None,
            work,
        )
    assert err.value.code == "error.verify_failed"
    assert any(b.endswith("deep.bin") for b in err.value.params["bad"])
    assert not (tmp_path / "out").exists()


def test_sign_failure_cleans_work_dir(tmp_paths, tmp_path, fake_cert):
    work = tmp_path / "work"
    with pytest.raises(WispError) as err:
        sign_ipa(
            SignRequest(make_ipa(tmp_path), fake_cert.id),
            CertStore(tmp_paths),
            tmp_path / "out",
            lambda s: None,
            _FailingRunner(),
            work,
        )
    assert err.value.code == "error.sign_failed"
    assert list(work.iterdir()) == []
    assert not (tmp_path / "out" / "Test-signed.ipa").exists()


def test_verify_failure_raises_verify_failed(tmp_paths, tmp_path, fake_cert):
    work = tmp_path / "work"
    steps = []
    with pytest.raises(WispError) as err:
        sign_ipa(
            SignRequest(make_ipa(tmp_path), fake_cert.id),
            CertStore(tmp_paths),
            tmp_path / "out",
            steps.append,
            _TamperingRunner(),
            work,
        )
    assert err.value.code == "error.verify_failed"
    assert err.value.params["bad"] == ["res.txt"]
    assert steps == ["extract", "sign", "verify"]
    assert list(work.iterdir()) == []


def test_password_not_in_error_detail(tmp_path):
    _, profile, password = make_pair()
    (tmp_path / "bad.p12").write_bytes(b"not a p12")
    (tmp_path / "p.mobileprovision").write_bytes(profile)
    app = make_app(tmp_path / "a")
    with pytest.raises(WispError) as err:
        ZsignRunner(zsign_path()).sign(
            app, tmp_path / "bad.p12", tmp_path / "p.mobileprovision", password
        )
    assert err.value.code == "error.sign_failed"
    assert err.value.detail and password not in err.value.detail
    assert password not in str(err.value)


def test_password_redacted_when_echoed(tmp_paths, tmp_path, fake_cert):
    p12, profile, password = CertStore(tmp_paths).materialize(fake_cert.id)
    missing = tmp_path / f"x{password}.app"  # zsign echoes the invalid path
    with pytest.raises(WispError) as err:
        ZsignRunner(zsign_path()).sign(missing, p12, profile, password)
    assert err.value.code == "error.sign_failed"
    assert "***" in err.value.detail and password not in err.value.detail


def test_zsign_missing(tmp_path):
    app = make_app(tmp_path / "a")
    with pytest.raises(WispError) as err:
        ZsignRunner(tmp_path / "nope.exe").sign(app, tmp_path, tmp_path, "pw")
    assert err.value.code == "error.zsign_missing"


def test_zsign_path_frozen_and_source(monkeypatch, tmp_path):
    assert zsign_path().is_file()
    assert zsign_path().parts[-3:] == ("vendor", "zsign", "zsign.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert zsign_path() == tmp_path / "zsign" / "zsign.exe"


def test_interrupt_cleans_work_dir_and_propagates(tmp_paths, tmp_path, fake_cert):
    work = tmp_path / "work"
    with pytest.raises(KeyboardInterrupt):
        _run(tmp_paths, tmp_path, fake_cert.id, _InterruptingRunner(), work)
    assert list(work.iterdir()) == []


def test_pack_failure_cleans_work_dir(tmp_paths, tmp_path, fake_cert, monkeypatch):
    def broken_pack(app_dir, out):
        out.write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(pipeline, "pack_ipa", broken_pack)
    work = tmp_path / "work"
    with pytest.raises(OSError, match="disk full"):
        _run(tmp_paths, tmp_path, fake_cert.id, None, work)
    assert list(work.iterdir()) == []
    assert not (tmp_path / "out").exists()


def test_read_only_files_are_removed(tmp_paths, tmp_path, fake_cert):
    work = tmp_path / "work"
    with pytest.raises(WispError, match="sign_failed"):
        _run(tmp_paths, tmp_path, fake_cert.id, _ReadOnlyFailingRunner(), work)
    assert list(work.iterdir()) == []


def test_cleanup_retries_transient_lock(tmp_paths, tmp_path, fake_cert, monkeypatch):
    real_rmtree = pipeline.shutil.rmtree
    calls = []

    def flaky_rmtree(path, **kwargs):
        calls.append(path)
        if len(calls) == 1:
            raise PermissionError("locked by scanner")
        real_rmtree(path, **kwargs)

    monkeypatch.setattr(pipeline.shutil, "rmtree", flaky_rmtree)
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)
    work = tmp_path / "work"
    with pytest.raises(WispError, match="sign_failed"):
        _run(tmp_paths, tmp_path, fake_cert.id, _FailingRunner(), work)
    assert len(calls) == 2 and list(work.iterdir()) == []


def test_cleanup_failure_logs_and_keeps_original_error(
    tmp_paths, tmp_path, fake_cert, monkeypatch, caplog
):
    def stuck_rmtree(path, **kwargs):
        raise PermissionError("locked by scanner")

    monkeypatch.setattr(pipeline.shutil, "rmtree", stuck_rmtree)
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)
    work = tmp_path / "work"
    with (
        caplog.at_level(logging.WARNING, logger=pipeline.__name__),
        pytest.raises(WispError) as err,
    ):
        _run(tmp_paths, tmp_path, fake_cert.id, _FailingRunner(), work)
    assert err.value.code == "error.sign_failed" and err.value.detail == "boom"
    (leftover,) = list(work.iterdir())
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and str(leftover) in warnings[0].getMessage()
