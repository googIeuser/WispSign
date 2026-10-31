import argparse
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import webview
from webview.dom import DOMEventHandler

from wispsign.bridge.api import WispApi, _is_link, _remove_link
from wispsign.paths import AppPaths

_log = logging.getLogger(__name__)

TITLE = "WispSign"
WINDOW_SIZE = (1280, 800)
MIN_SIZE = (1024, 680)
BACKGROUND = "#0b0b0b"
_WORK_DIR_NAME = re.compile(r"[a-z0-9]{4}")

STALE_AFTER_SECONDS = 6 * 60 * 60


def ui_index_path() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "ui" / "index.html"
    return Path(__file__).resolve().parents[2] / "ui" / "dist" / "index.html"


class Emitter:
    def __init__(self) -> None:
        self._window: Any = None
        self._lock = threading.Lock()

    def attach(self, window: Any) -> None:
        with self._lock:
            self._window = window

    def detach(self, *_: Any) -> None:
        with self._lock:
            self._window = None

    def __call__(self, event: dict) -> None:
        with self._lock:
            window = self._window
        if window is None:
            return
        try:
            window.evaluate_js("window.__wisp(" + json.dumps(event) + ")")
        except Exception:  # noqa: BLE001 - a dead UI must never break the caller
            _log.warning("emit failed", exc_info=True)


def handle_drop(api: Any, emit: Callable[[dict], None], event: Any) -> None:
    try:
        files = event["dataTransfer"]["files"]
    except (KeyError, TypeError):
        return
    if not isinstance(files, list) or not files:
        return
    added = ignored = unresolved = 0
    errors: list[dict] = []
    for file in files:
        name = str(file.get("name", "")) if isinstance(file, dict) else ""
        if not name.lower().endswith(".ipa"):
            ignored += 1
            continue
        path = file.get("pywebviewFullPath")
        if not isinstance(path, str) or not path:
            unresolved += 1
            continue
        result = api.library_add_path(path)
        if result.get("ok"):
            added += 1
        else:
            errors.append(result["error"])
    emit(
        {
            "type": "library_changed",
            "added": added,
            "ignored": ignored,
            "unresolved": unresolved,
            "errors": errors,
        }
    )


def _rmtree_quiet(path: Path) -> None:
    try:
        if _is_link(path):
            _remove_link(path)
        else:
            shutil.rmtree(path)
    except OSError as exc:
        _log.warning("sweep skipped %s: %s", path.name, type(exc).__name__)


def _is_stale(path: Path, now: float) -> bool:
    try:
        return path.is_dir() and now - path.lstat().st_mtime > STALE_AFTER_SECONDS
    except OSError:
        return False


def _work_root() -> Path | None:
    base = os.environ.get("LOCALAPPDATA", "")
    return Path(base) / "WS" if base and Path(base).is_absolute() else None


def sweep_stale(paths: AppPaths, work_root: Path | None = None) -> None:
    root = work_root or _work_root()
    signed = paths.cache / "signed"
    now = time.time()
    stale: list[Path] = []
    try:
        if root is not None and root.is_dir() and not _is_link(root):
            stale += [
                p
                for p in root.iterdir()
                if _WORK_DIR_NAME.fullmatch(p.name) and _is_stale(p, now)
            ]
        if signed.is_dir() and not _is_link(signed):
            stale += [p for p in signed.iterdir() if _is_stale(p, now)]
    except OSError as exc:
        _log.warning("sweep could not list directories: %s", type(exc).__name__)
        return
    for path in stale:
        _rmtree_quiet(path)


def register_drop(window: Any, handler: DOMEventHandler) -> None:
    try:
        drop = window.dom.document.events.drop
        if handler in getattr(drop, "_items", ()):
            return
        drop += handler
    except Exception:  # noqa: BLE001 - a missing drop handler must not break the UI
        _log.warning("drop handler registration failed", exc_info=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wispsign")
    parser.add_argument("--debug", action="store_true", help="enable devtools")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    paths = AppPaths.default()
    paths.ensure()
    sweep_stale(paths)

    emitter = Emitter()
    api = WispApi(paths, emit=emitter)
    window = webview.create_window(
        TITLE,
        url=str(ui_index_path()),
        js_api=api,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=MIN_SIZE,
        background_color=BACKGROUND,
    )
    api._bind_window(window)

    drop_handler = DOMEventHandler(
        lambda event: handle_drop(api, emitter, event), prevent_default=True
    )

    def on_loaded() -> None:
        emitter.attach(window)
        register_drop(window, drop_handler)

    window.events.loaded += on_loaded
    window.events.closed += emitter.detach
    webview.start(debug=args.debug, http_server=True)
    return 0
