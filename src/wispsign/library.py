pass

import plistlib
import posixpath
import shutil
import threading
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.parsers.expat import ExpatError

from wispsign.errors import WispError
from wispsign.paths import AppPaths
from wispsign.repos.models import RepoApp
from wispsign.storage import JsonStore

MAX_PLIST_BYTES = 8 * 1024 * 1024
MAX_ICON_BYTES = 8 * 1024 * 1024
_ID_LEN = 12


@dataclass(frozen=True)
class LibraryEntry:
    id: str
    name: str
    bundle_id: str
    version: str
    path: str
    source: str
    added_at: str
    owned: bool = True


_Entries = list[LibraryEntry]


def _legacy_owned(path: object) -> bool:
    pass
    return isinstance(path, str) and not Path(path).is_absolute()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _invalid(detail: str) -> WispError:
    return WispError("error.ipa_invalid", detail)


def _read_limited(zf: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    if info.file_size > limit:
        raise _invalid(f"entry too large: {info.filename}")
    with zf.open(info) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise _invalid(f"entry too large: {info.filename}")
    return data


def _find_info_plist(zf: zipfile.ZipFile) -> zipfile.ZipInfo:
    for info in zf.infolist():
        parts = info.filename.split("/")
        if (
            len(parts) == 3
            and parts[0] == "Payload"
            and parts[1].endswith(".app")
            and parts[2] == "Info.plist"
        ):
            return info
    raise _invalid("no Payload/*.app/Info.plist")


def _icon_bases(info: dict) -> list[str]:
    icons = info.get("CFBundleIcons")
    primary = icons.get("CFBundlePrimaryIcon") if isinstance(icons, dict) else None
    names = primary.get("CFBundleIconFiles") if isinstance(primary, dict) else None
    if not isinstance(names, list):
        return []
    return [n.removesuffix(".png") for n in names if isinstance(n, str)]


def _largest_icon(zf: zipfile.ZipFile, app_dir: str, bases: list[str]) -> bytes | None:
    best: zipfile.ZipInfo | None = None
    for item in zf.infolist():
        if posixpath.dirname(item.filename) != app_dir:
            continue
        leaf = posixpath.basename(item.filename)
        is_icon = leaf.endswith(".png") and any(leaf.startswith(b) for b in bases)
        if is_icon and (best is None or item.file_size > best.file_size):
            best = item
    if best is None or best.file_size > MAX_ICON_BYTES:
        return None
    return _read_limited(zf, best, MAX_ICON_BYTES)


def _inspect(ipa: Path) -> tuple[dict, bytes | None]:
    pass
    try:
        with zipfile.ZipFile(ipa) as zf:
            member = _find_info_plist(zf)
            try:
                info = plistlib.loads(_read_limited(zf, member, MAX_PLIST_BYTES))
            except (plistlib.InvalidFileException, ValueError, ExpatError) as exc:
                raise _invalid(f"unreadable Info.plist: {type(exc).__name__}") from exc
            if not isinstance(info, dict) or not isinstance(
                info.get("CFBundleIdentifier"), str
            ):
                raise _invalid("Info.plist has no CFBundleIdentifier")
            icon = _largest_icon(
                zf, posixpath.dirname(member.filename), _icon_bases(info)
            )
            return info, icon
    except zipfile.BadZipFile as exc:
        raise _invalid("not a zip file") from exc
    except OSError as exc:
        raise WispError("error.io", type(exc).__name__) from exc


def _display_name(info: dict, fallback: str) -> str:
    return str(info.get("CFBundleDisplayName") or info.get("CFBundleName") or fallback)


def _version(info: dict) -> str:
    return str(
        info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""
    )


class Library:
    def __init__(self, paths: AppPaths):
        self._paths = paths
        self._store = JsonStore(paths.library, [])
        self._lock = threading.Lock()



    def list(self) -> _Entries:
        data = self._store.load()
        entries: list[LibraryEntry] = []
        for row in data if isinstance(data, list) else []:
            if not isinstance(row, dict):
                continue
            if "owned" not in row:
                row = {**row, "owned": _legacy_owned(row.get("path"))}
            else:
                row = {**row, "owned": row["owned"] is True}
            try:
                entries.append(LibraryEntry(**row))
            except TypeError:
                continue
        return entries

    def get(self, id: str) -> LibraryEntry:
        for entry in self.list():
            if entry.id == id:
                return entry
        raise WispError("error.entry_not_found")

    def icon(self, id: str) -> bytes | None:
        try:
            return self._icon_file(id).read_bytes()
        except OSError:
            return None



    def add_file(self, ipa: Path) -> LibraryEntry:
        info, icon = _inspect(ipa)
        entry_id = uuid.uuid4().hex[:_ID_LEN]
        name = f"{entry_id}.ipa"
        self._copy_in(ipa, name)
        return self._insert(
            LibraryEntry(
                entry_id,
                _display_name(info, ipa.stem),
                info["CFBundleIdentifier"],
                _version(info),
                name,
                "file",
                _now(),
            ),
            icon,
        )

    def add_download(self, app: RepoApp, path: Path) -> LibraryEntry:
        pass
        try:
            _, icon = _inspect(path)
        except WispError:
            path.unlink(missing_ok=True)
            raise

        if path.parent.resolve() == self._paths.ipas.resolve():
            name = path.name
        else:
            name = str(path.resolve())
        return self._insert(
            LibraryEntry(
                uuid.uuid4().hex[:_ID_LEN],
                app.name,
                app.bundle_id,
                app.version,
                name,
                app.repo_url,
                _now(),
            ),
            icon,
        )

    def remove(self, id: str) -> None:
        with self._lock:
            entries = self.list()
            target = next((e for e in entries if e.id == id), None)
            if target is None:
                return
            self._save([e for e in entries if e.id != id])
        if target.owned:
            (self._paths.ipas / target.path).unlink(missing_ok=True)
        self._icon_file(id).unlink(missing_ok=True)



    def _copy_in(self, source: Path, name: str) -> None:
        try:
            self._paths.ipas.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, self._paths.ipas / name)
        except OSError as exc:
            raise WispError("error.io", type(exc).__name__) from exc

    def _icon_file(self, id: str) -> Path:
        return self._paths.cache / "icons" / f"{Path(id).name}.png"

    def _save(self, entries: _Entries) -> None:
        self._store.save([asdict(e) for e in entries])

    def _insert(self, entry: LibraryEntry, icon: bytes | None) -> LibraryEntry:
        with self._lock:
            others = [e for e in self.list() if e.id != entry.id]
            self._save([*others, entry])
        if icon is not None:
            target = self._icon_file(entry.id)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(icon)
        return entry
