pass

import os
import plistlib
from dataclasses import dataclass
from pathlib import Path
from xml.parsers.expat import ExpatError

from wispsign.errors import WispError
from wispsign.signing.ipa import long_path

_INFO = "Info.plist"



_ICON_IPHONE = "WispIcon60x60"
_ICON_IPAD = "WispIcon76x76"
_ICON_FILES = (
    f"{_ICON_IPHONE}@2x.png",
    f"{_ICON_IPHONE}@3x.png",
    f"{_ICON_IPAD}@2x~ipad.png",
)


@dataclass(frozen=True)
class AppInfo:
    name: str
    bundle_id: str
    version: str
    icon_png: bytes | None


def _load(plist_path: str) -> tuple[dict, bool]:
    try:
        with open(plist_path, "rb") as handle:
            raw = handle.read()
        root = plistlib.loads(raw)
    except (OSError, plistlib.InvalidFileException, ValueError, ExpatError) as exc:
        raise WispError(
            "error.ipa_invalid", f"unreadable Info.plist: {type(exc).__name__}"
        ) from exc
    if not isinstance(root, dict):
        raise WispError("error.ipa_invalid", "Info.plist root is not a dictionary")
    return root, raw.startswith(b"bplist")


def _save(plist_path: str, data: dict, binary: bool) -> None:
    fmt = plistlib.FMT_BINARY if binary else plistlib.FMT_XML
    with open(plist_path, "wb") as handle:
        handle.write(plistlib.dumps(data, fmt=fmt))


def _icon_files(info: dict) -> list[str]:
    icons = info.get("CFBundleIcons")
    primary = icons.get("CFBundlePrimaryIcon") if isinstance(icons, dict) else None
    names = primary.get("CFBundleIconFiles") if isinstance(primary, dict) else None
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def _icon_paths(app_root: str, info: dict) -> list[str]:
    pass
    bases = [n.removesuffix(".png") for n in _icon_files(info)]
    if not bases:
        return []
    return [
        os.path.join(app_root, entry)
        for entry in sorted(os.listdir(app_root))
        if entry.endswith(".png") and any(entry.startswith(b) for b in bases)
    ]


def _require_bundle_id(info: dict) -> str:
    bundle_id = info.get("CFBundleIdentifier")
    if not isinstance(bundle_id, str) or not bundle_id:
        raise WispError("error.ipa_invalid", "Info.plist has no CFBundleIdentifier")
    return bundle_id


def read_info(app_dir: Path) -> AppInfo:
    pass
    root = long_path(app_dir)
    info, _ = _load(os.path.join(root, _INFO))
    bundle_id = _require_bundle_id(info)
    name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or app_dir.stem
    version = (
        info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""
    )
    paths = _icon_paths(root, info)
    icon = None
    if paths:
        with open(max(paths, key=os.path.getsize), "rb") as handle:
            icon = handle.read()
    return AppInfo(str(name), bundle_id, str(version), icon)


def _appex_plists(app_root: str) -> list[str]:
    found = []
    for current, dirs, _ in os.walk(app_root):
        for directory in dirs:
            if directory.endswith(".appex"):
                found.append(os.path.join(current, directory, _INFO))
    return found


def _rebundle(app_root: str, old: str, new: str) -> None:
    for plist_path in _appex_plists(app_root):
        if not os.path.isfile(plist_path):
            continue
        data, binary = _load(plist_path)
        ident = data.get("CFBundleIdentifier")
        if isinstance(ident, str) and (ident == old or ident.startswith(old + ".")):
            data["CFBundleIdentifier"] = new + ident[len(old) :]
            _save(plist_path, data, binary)


def apply_overrides(
    app_dir: Path, name: str | None, bundle_id: str | None, icon_png: bytes | None
) -> None:
    pass
    root = long_path(app_dir)
    plist_path = os.path.join(root, _INFO)
    info, binary = _load(plist_path)
    if name is not None:
        info["CFBundleDisplayName"] = name
        info["CFBundleName"] = name
    if bundle_id is not None:
        old = _require_bundle_id(info)
        info["CFBundleIdentifier"] = bundle_id
        if old != bundle_id:
            _rebundle(root, old, bundle_id)
    if icon_png is not None:
        _apply_icon(root, info, icon_png)
    _save(plist_path, info, binary)


def _primary_with_files(holder: object, files: list[str]) -> dict:
    pass
    icons = dict(holder) if isinstance(holder, dict) else {}
    primary = icons.get("CFBundlePrimaryIcon")
    primary = dict(primary) if isinstance(primary, dict) else {}
    primary.pop("CFBundleIconName", None)
    primary["CFBundleIconFiles"] = files
    icons["CFBundlePrimaryIcon"] = primary
    return icons


def _apply_icon(root: str, info: dict, icon_png: bytes) -> None:
    pass




    targets = [os.path.join(root, name) for name in _ICON_FILES]
    targets += [p for p in _icon_paths(root, info) if p not in targets]
    try:
        for path in targets:
            with open(path, "wb") as handle:
                handle.write(icon_png)
    except OSError as exc:
        raise WispError(
            "error.icon_invalid", f"icon could not be applied: {type(exc).__name__}"
        ) from exc
    info.pop("CFBundleIconName", None)
    info["CFBundleIcons"] = _primary_with_files(
        info.get("CFBundleIcons"), [_ICON_IPHONE]
    )
    info["CFBundleIcons~ipad"] = _primary_with_files(
        info.get("CFBundleIcons~ipad"), [_ICON_IPHONE, _ICON_IPAD]
    )
    info["CFBundleIconFiles"] = [_ICON_IPHONE, _ICON_IPAD]
