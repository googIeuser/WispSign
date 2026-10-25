"""JS-facing API exposed through pywebview.

Every public method returns a JSON-safe envelope and never raises:
``{"ok": True, "data": ...}`` or ``{"ok": False, "error": {code, params, detail}}``.
Job-starting methods return a job id; fetch its terminal event with job_result.
All attributes and helpers start with ``_`` so pywebview does not expose them.
"""

import base64
import functools
import importlib.metadata
import logging
import os
import shutil
import stat
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from wispsign.bridge.jobs import Emit, JobRunner
from wispsign.bridge.serial import jsonable
from wispsign.certs.store import CertStore
from wispsign.device.service import DeviceService
from wispsign.errors import WispError, map_error
from wispsign.library import Library
from wispsign.paths import AppPaths
from wispsign.repos.client import RepoClient
from wispsign.repos.models import Repo, RepoApp
from wispsign.signing.pipeline import SignRequest, sign_ipa
from wispsign.storage import JsonStore
from wispsign.updates import check_latest, update_repo

_log = logging.getLogger(__name__)

MAX_ICON_BYTES = 8 * 1024 * 1024
PNG_SIGNATURE = bytes([0x89]) + b"PNG\r\n" + bytes([0x1A]) + b"\n"
LANGUAGES = ("tr", "en")
_BLOCKING_CERT_ERRORS = {
    "warn.expired": "error.cert_expired",
    "warn.device_missing": "error.profile_device_missing",
    "warn.app_id_mismatch": "error.profile_app_id_mismatch",
}
_FILE_TYPES = {
    "ipa": ("IPA files (*.ipa)",),
    "p12": ("Certificates (*.p12;*.pfx)",),
    "mobileprovision": ("Provisioning profiles (*.mobileprovision)",),
    "png": ("PNG images (*.png)",),
}


class Dialogs(Protocol):
    def open_files(self, kind: str, multiple: bool) -> list[str]: ...

    def pick_folder(self) -> str | None: ...


class PywebviewDialogs:
    """Native open-file dialogs; bind the window once pywebview created it."""

    def __init__(self) -> None:
        self._window: Any = None

    def bind_window(self, window: Any) -> None:
        self._window = window

    def open_files(self, kind: str, multiple: bool) -> list[str]:
        if self._window is None or kind not in _FILE_TYPES:
            return []
        import webview

        picked = self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=multiple, file_types=_FILE_TYPES[kind]
        )
        return [str(p) for p in picked or ()]

    def pick_folder(self) -> str | None:
        if self._window is None:
            return None
        import webview

        picked = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return str(picked[0]) if picked else None


def _error_body(exc: BaseException) -> dict:
    err = map_error(exc)
    return {"code": err.code, "params": jsonable(err.params), "detail": err.detail}


def _envelope(fn: Callable[..., Any]) -> Callable[..., dict]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            return {"ok": True, "data": jsonable(fn(*args, **kwargs))}
        except Exception as exc:  # noqa: BLE001 - the bridge never raises
            return {"ok": False, "error": _error_body(exc)}

    return wrapper


def _app_version() -> str:
    try:
        return importlib.metadata.version("wispsign")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _usable_dir(value: object) -> bool:
    """Absolute, existing, writable directory."""
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return path.is_absolute() and path.is_dir() and os.access(path, os.W_OK)


def _read_icon(icon_path: str | None) -> bytes | None:
    if not icon_path:
        return None
    try:
        data = Path(icon_path).read_bytes()
    except OSError as exc:
        raise WispError("error.io", type(exc).__name__) from exc
    if len(data) > MAX_ICON_BYTES:
        raise WispError("error.icon_invalid", "icon too large")
    if not data.startswith(PNG_SIGNATURE):
        raise WispError("error.icon_invalid", "not a PNG file")
    return data


def _is_link(path: Path) -> bool:
    """Symlink, junction or any other reparse point: never descend into it."""
    if path.is_symlink() or path.is_junction():
        return True
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _remove_link(path: Path) -> None:
    """Delete only the link itself, never its target."""
    try:
        path.unlink()
    except (IsADirectoryError, PermissionError):
        os.rmdir(path)  # directory junction/symlink: removes the link only


def _purge(directory: Path, keep: frozenset[Path]) -> int:
    """Delete everything under directory except `keep`; return the bytes freed.

    Links (symlinks, junctions, other reparse points) are removed without
    being followed. Entries that cannot be deleted (for example in use) are
    skipped and logged.
    """
    freed = 0
    for child in directory.iterdir():
        if child in keep:
            continue
        try:
            if _is_link(child):
                _remove_link(child)
                continue
            if child.is_dir():
                freed += _purge(child, keep)
                try:
                    child.rmdir()  # fails while something kept is inside
                except OSError:
                    pass
                continue
            size = child.lstat().st_size
            child.unlink()
        except OSError as exc:
            _log.warning("cache_clear skipped %s: %s", child.name, type(exc).__name__)
            continue
        freed += size
    return freed


class WispApi:
    def __init__(
        self,
        paths: AppPaths,
        repos: RepoClient | None = None,
        certs: CertStore | None = None,
        devices: DeviceService | None = None,
        library: Library | None = None,
        dialogs: Dialogs | None = None,
        emit: Emit | None = None,
        sign: Callable[..., Path] = sign_ipa,
        http: httpx.Client | None = None,
    ):
        self._paths = paths
        self._repos = repos or RepoClient(paths)
        self._certs = certs or CertStore(paths)
        self._devices = devices or DeviceService()
        self._library = library or Library(paths)
        self._dialogs: Dialogs = dialogs or PywebviewDialogs()
        self._sign = sign
        self._http = http
        self._jobs = JobRunner(emit or (lambda event: None))
        # language None = never chosen: the UI then follows the system language.
        self._defaults = {"language": None, "download_dir": str(paths.ipas)}
        self._settings = JsonStore(paths.settings, self._defaults)
        self._settings_lock = threading.Lock()
        self._active_outputs: set[Path] = set()
        self._active_lock = threading.Lock()

    def _start(self, fn: Callable[[Callable[[dict], None]], Any]) -> str:
        return self._jobs.start(lambda progress: jsonable(fn(progress)))

    def _bind_window(self, window: Any) -> None:
        bind = getattr(self._dialogs, "bind_window", None)
        if bind:
            bind(window)

    # --- state / settings -------------------------------------------

    @_envelope
    def get_state(self) -> dict:
        return {
            "version": _app_version(),
            "settings": self._load_settings(),
            "repos": self._repos.list_urls(),
            "library": self._library.list(),
            "certs": self._certs.list(),
            "updates": update_repo() is not None,  # off unless a release repo is set
        }

    def _load_settings(self) -> dict:
        stored = self._settings.load()
        merged = dict(self._defaults)
        if isinstance(stored, dict):
            merged.update({k: v for k, v in stored.items() if k in merged})
        return merged

    @_envelope
    def settings_get(self) -> dict:
        return self._load_settings()

    @_envelope
    def settings_set(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            raise WispError("error.settings_invalid", "patch must be an object")
        for key, value in patch.items():
            if key == "language" and value in LANGUAGES:
                continue
            if key == "download_dir" and _usable_dir(value):
                continue
            raise WispError("error.settings_invalid", f"bad setting: {key}")
        with self._settings_lock:
            merged = {**self._load_settings(), **patch}
            self._settings.save(merged)
        return merged

    @_envelope
    def cache_clear(self) -> int:
        """Empty paths.cache and return the bytes freed.

        Kept: the icons of current library entries (extracted once at import,
        they cannot be rebuilt from the cache) and the output folders of
        running sign jobs. Library IPAs, certificates and settings live outside
        the cache and are never touched.
        """
        cache = self._paths.cache
        if not cache.is_dir():
            return 0
        if _is_link(cache):
            raise WispError("error.io", "cache folder is a link")
        icons = cache / "icons"
        keep = {icons / f"{entry.id}.png" for entry in self._library.list()}
        with self._active_lock:
            return _purge(cache, frozenset(keep | self._active_outputs))

    @_envelope
    def check_update(self) -> dict:
        current = _app_version()
        result = check_latest(current, http=self._http)
        return {"current": current, "status": result.status, "latest": result.latest}

    # --- repos --------------------------------------------------------

    @_envelope
    def repos_list(self) -> list[str]:
        return self._repos.list_urls()

    @_envelope
    def repos_add(self, url: str) -> Repo:
        return self._repos.add(url)

    @_envelope
    def repos_remove(self, url: str) -> None:
        self._repos.remove(url)

    @_envelope
    def repos_refresh(self) -> str:
        def run(progress: Callable[[dict], None]) -> list:
            return [
                {"error": _error_body(r)} if isinstance(r, WispError) else jsonable(r)
                for r in self._repos.refresh_all()
            ]

        return self._start(run)

    @_envelope
    def repo_download(self, repo_url: str, bundle_id: str) -> str:
        def run(progress: Callable[[dict], None]) -> Any:
            app = self._find_app(repo_url, bundle_id)

            sent = -1  # last percent sent; chunks arrive far more often than that

            def on_bytes(done: int, total: int | None) -> None:
                nonlocal sent
                if not total:
                    return
                percent = min(100, done * 100 // total)
                if percent != sent:
                    sent = percent
                    progress({"step": "download", "percent": percent})

            dest = Path(self._load_settings()["download_dir"])
            path = self._repos.download(app, dest, on_bytes)
            return self._library.add_download(app, path)

        return self._start(run)

    def _find_app(self, repo_url: str, bundle_id: str) -> RepoApp:
        if repo_url not in self._repos.list_urls():
            raise WispError("error.repo_invalid", "unknown repo")
        for app in self._repos.cached(repo_url).apps:
            if app.bundle_id == bundle_id:
                return app
        raise WispError("error.repo_invalid", "app not found in repo")

    @_envelope
    def job_result(self, job_id: str) -> dict | None:
        """Terminal event of a job, or None while it runs.

        A fast job may finish before the UI received its id, so the UI must
        call this right after getting the id (or buffer events by job id).
        """
        return self._jobs.result(job_id)

    # --- library ------------------------------------------------------

    @_envelope
    def library_list(self) -> list:
        return self._library.list()

    @_envelope
    def library_add_files(self) -> list:
        picked = self._dialogs.open_files("ipa", True)
        return [self._library.add_file(Path(p)) for p in picked]

    @_envelope
    def library_add_path(self, path: str) -> Any:
        return self._library.add_file(Path(path))

    @_envelope
    def library_remove(self, id: str) -> None:
        self._library.remove(id)

    @_envelope
    def library_icon(self, id: str) -> str | None:
        data = self._library.icon(id)
        if data is None:
            return None
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")

    @_envelope
    def pick_folder(self) -> str | None:
        """Folder chosen in the native dialog (None if cancelled); not saved here."""
        return self._dialogs.pick_folder()

    @_envelope
    def pick_icon(self) -> str | None:
        picked = self._dialogs.open_files("png", False)
        return picked[0] if picked else None

    # --- certificates -------------------------------------------------

    @_envelope
    def certs_list(self) -> list:
        return self._certs.list()

    @_envelope
    def certs_import(self, nickname: str, password: str) -> Any:
        p12 = self._dialogs.open_files("p12", False)
        if not p12:
            return None
        profile = self._dialogs.open_files("mobileprovision", False)
        if not profile:
            return None
        try:
            p12_bytes = Path(p12[0]).read_bytes()
            profile_bytes = Path(profile[0]).read_bytes()
        except OSError as exc:
            raise WispError("error.io", type(exc).__name__) from exc
        return self._certs.import_pair(p12_bytes, profile_bytes, password, nickname)

    @_envelope
    def certs_remove(self, id: str) -> None:
        self._certs.remove(id)

    @_envelope
    def certs_validate(
        self, id: str, udid: str | None, bundle_id: str | None = None
    ) -> list:
        """Warnings for the cert; pass ``bundle_id`` to check it against the App ID."""
        return self._certs.validate(id, udid, datetime.now(UTC), bundle_id or None)

    # --- device -------------------------------------------------------

    @_envelope
    def device_list(self) -> list:
        return self._devices.list_devices()

    @_envelope
    def device_apps(self, udid: str) -> list:
        return self._devices.list_apps(udid)

    @_envelope
    def device_uninstall(self, udid: str, bundle_id: str) -> None:
        self._devices.uninstall(bundle_id, udid)

    # --- sign and install ---------------------------------------------

    @_envelope
    def sign_and_install(
        self,
        entry_id: str,
        cert_id: str,
        udid: str,
        name: str | None,
        bundle_id: str | None,
        icon_path: str | None,
    ) -> str:
        def run(progress: Callable[[dict], None]) -> None:
            entry = self._library.get(entry_id)
            warnings = self._certs.validate(
                cert_id, udid, datetime.now(UTC), bundle_id or entry.bundle_id
            )
            for warning in warnings:
                if code := _BLOCKING_CERT_ERRORS.get(warning.code):
                    raise WispError(code, **warning.params)
            request = SignRequest(
                ipa=self._paths.ipas / entry.path,
                cert_id=cert_id,
                name=name or None,
                bundle_id=bundle_id or None,
                icon_png=_read_icon(icon_path),
            )
            root = self._paths.cache / "signed"
            with self._active_lock:  # cache_clear must not race the new folder
                root.mkdir(parents=True, exist_ok=True)
                # per job: no name clashes; keyed as cache_clear walks it
                out_dir = root / Path(tempfile.mkdtemp(dir=root)).name
                self._active_outputs.add(out_dir)
            try:
                signed = self._sign(
                    request, self._certs, out_dir, lambda step: progress({"step": step})
                )
                progress({"step": "install", "percent": 0})
                self._devices.install(
                    signed,
                    udid,
                    lambda p: progress({"step": "install", "percent": p}),
                )
            finally:
                shutil.rmtree(out_dir, ignore_errors=True)
                with self._active_lock:
                    self._active_outputs.discard(out_dir)

        return self._start(run)
