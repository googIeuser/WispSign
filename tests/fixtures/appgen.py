"""Builders for minimal unsigned .app bundles and IPAs (test fixtures)."""

import os
import plistlib
from pathlib import Path

from macho_stub import build_arm64_stub

from wispsign.signing.ipa import long_path, pack_ipa

# 1x1 transparent PNG
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea7d6054200000000"
    "49454e44ae426082"
)
APP_NAME = "Test"
ICON_NAME = "AppIcon60x60"
_PIECE = 50


def _put(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def _deep_resource(app: Path, deep_path_len: int) -> str:
    """Path of a file inside ``app`` whose plain path length reaches the target."""
    base = os.path.abspath(app)
    parts: list[str] = []
    length = len(base) + len(os.sep + "deep.bin")
    while length < deep_path_len:
        piece = "d" * min(_PIECE, max(1, deep_path_len - length - 1))
        parts.append(piece)
        length += len(os.sep) + len(piece)
    return os.path.join(long_path(app), *parts, "deep.bin")


def make_app(
    root: Path,
    bundle_id: str = "com.test.app",
    deep_path_len: int = 0,
    with_appex: bool = True,
) -> Path:
    """Create ``root/Test.app`` and return it."""
    app = root / f"{APP_NAME}.app"
    base = long_path(app)
    stub = build_arm64_stub()
    info = {
        "CFBundleIdentifier": bundle_id,
        "CFBundleName": APP_NAME,
        "CFBundleExecutable": APP_NAME,
        "CFBundleShortVersionString": "1.0",
        "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconFiles": [ICON_NAME]}},
    }
    _put(os.path.join(base, "Info.plist"), plistlib.dumps(info))
    _put(os.path.join(base, APP_NAME), stub)
    _put(os.path.join(base, f"{ICON_NAME}@2x.png"), PNG_1X1)
    _put(os.path.join(base, "res.txt"), b"resource")
    if with_appex:
        appex = os.path.join(base, "PlugIns", "Ext.appex")
        ext = {
            "CFBundleIdentifier": f"{bundle_id}.Ext",
            "CFBundleName": "Ext",
            "CFBundleExecutable": "Ext",
        }
        _put(os.path.join(appex, "Info.plist"), plistlib.dumps(ext))
        _put(os.path.join(appex, "Ext"), stub)
    if deep_path_len:
        _put(_deep_resource(app, deep_path_len), b"deep")
    return app


def make_ipa(root: Path, **kwargs: object) -> Path:
    """Build an app under ``root/src`` and zip it to ``root/Test.ipa``."""
    app = make_app(root / "src", **kwargs)
    return pack_ipa(app, root / f"{APP_NAME}.ipa")
