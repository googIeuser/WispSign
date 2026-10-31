import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from wispsign.certs.p12 import load_p12
from wispsign.certs.profile import parse_profile
from wispsign.errors import WispError
from wispsign.paths import AppPaths
from wispsign.secrets import protect, unprotect
from wispsign.storage import JsonStore

WARN_CODES: tuple[str, ...] = (
    "warn.expired",
    "warn.expires_soon",
    "warn.device_missing",
    "warn.no_push",
    "warn.app_id_mismatch",
)


EXPIRES_SOON_DAYS = 14
_ID_RE = re.compile(r"[0-9a-f]{12}")
_P12_FILE = "cert.p12"
_PROFILE_FILE = "profile.mobileprovision"
_META_FILE = "meta.json"
_TMP_PREFIX = ".tmp-"


@dataclass(frozen=True)
class CertRecord:
    id: str
    nickname: str
    team_id: str
    common_name: str
    app_id: str
    is_wildcard: bool
    has_push: bool
    devices: tuple[str, ...]
    expires: datetime
    added_at: datetime
    broken: bool = False
    all_devices: bool = False


@dataclass(frozen=True)
class CertWarning:
    code: str
    params: dict


def covers_device(
    devices: tuple[str, ...], udid: str, all_devices: bool = False
) -> bool:
    return all_devices or udid.casefold() in {d.casefold() for d in devices}


def app_id_matches(app_id: str, bundle_id: str) -> bool:
    if app_id.endswith("*"):
        return bundle_id.startswith(app_id[:-1])
    return app_id == bundle_id


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _from_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _record_to_meta(record: CertRecord, password_dpapi: str) -> dict:
    return {
        "id": record.id,
        "nickname": record.nickname,
        "team_id": record.team_id,
        "common_name": record.common_name,
        "app_id": record.app_id,
        "is_wildcard": record.is_wildcard,
        "has_push": record.has_push,
        "devices": list(record.devices),
        "all_devices": record.all_devices,
        "expires": _to_iso(record.expires),
        "added_at": _to_iso(record.added_at),
        "password_dpapi": password_dpapi,
    }


def _meta_to_record(meta: object) -> CertRecord:
    try:
        return CertRecord(
            id=meta["id"],
            nickname=meta["nickname"],
            team_id=meta["team_id"],
            common_name=meta["common_name"],
            app_id=meta["app_id"],
            is_wildcard=bool(meta["is_wildcard"]),
            has_push=bool(meta["has_push"]),
            devices=tuple(meta["devices"]),
            all_devices=meta.get("all_devices") is True,
            expires=_from_iso(meta["expires"]),
            added_at=_from_iso(meta["added_at"]),
        )
    except (KeyError, TypeError, ValueError):
        raise WispError("error.cert_meta_corrupt") from None


def _broken_record(folder: Path) -> CertRecord:
    try:
        stamp = datetime.fromtimestamp(folder.stat().st_mtime, UTC)
    except OSError:
        stamp = datetime.fromtimestamp(0, UTC)
    stamp = stamp.replace(microsecond=0)
    return CertRecord(
        id=folder.name,
        nickname=folder.name,
        team_id="",
        common_name="",
        app_id="",
        is_wildcard=False,
        has_push=False,
        devices=(),
        expires=stamp,
        added_at=stamp,
        broken=True,
    )


_Records = list[CertRecord]
_Warnings = list[CertWarning]


class CertStore:
    def __init__(self, paths: AppPaths):
        self._root = paths.certs

    def import_pair(
        self, p12: bytes, profile: bytes, password: str, nickname: str
    ) -> CertRecord:
        p12_info = load_p12(p12, password)
        profile_info = parse_profile(profile)
        if p12_info.fingerprint not in profile_info.cert_fingerprints:
            raise WispError("error.cert_profile_mismatch")
        record = CertRecord(
            id=uuid.uuid4().hex[:12],
            nickname=nickname,
            team_id=profile_info.team_id,
            common_name=p12_info.common_name,
            app_id=profile_info.app_id,
            is_wildcard=profile_info.is_wildcard,
            has_push=profile_info.has_push,
            devices=profile_info.devices,
            all_devices=profile_info.all_devices,
            expires=min(p12_info.expires, profile_info.expires),
            added_at=datetime.now(UTC).replace(microsecond=0),
        )
        self._root.mkdir(parents=True, exist_ok=True)
        tmp = self._root / f"{_TMP_PREFIX}{record.id}"
        try:
            tmp.mkdir()
            (tmp / _P12_FILE).write_bytes(p12)
            (tmp / _PROFILE_FILE).write_bytes(profile)
            JsonStore(tmp / _META_FILE, None).save(
                _record_to_meta(record, protect(password))
            )
            tmp.rename(self._root / record.id)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return record

    def list(self) -> _Records:
        records: list[CertRecord] = []
        if not self._root.is_dir():
            return records
        for folder in self._root.iterdir():
            if not _ID_RE.fullmatch(folder.name) or not folder.is_dir():
                continue
            try:
                record = _meta_to_record(self._load_meta(folder))
            except WispError:
                record = _broken_record(folder)
            if record.id != folder.name:
                record = _broken_record(folder)
            records.append(record)
        return sorted(records, key=lambda r: (r.added_at, r.id))

    def remove(self, id: str) -> None:
        shutil.rmtree(self._folder(id))

    def materialize(self, id: str) -> tuple[Path, Path, str]:
        folder = self._folder(id)
        blob = self._load_meta(folder).get("password_dpapi")
        if not isinstance(blob, str):
            raise WispError("error.cert_meta_corrupt")
        return folder / _P12_FILE, folder / _PROFILE_FILE, unprotect(blob)

    def validate(
        self,
        id: str,
        device_udid: str | None,
        now: datetime,
        bundle_id: str | None = None,
    ) -> _Warnings:
        record = _meta_to_record(self._load_meta(self._folder(id)))
        warnings: list[CertWarning] = []
        remaining = record.expires - now
        if remaining.total_seconds() <= 0:
            warnings.append(CertWarning("warn.expired", {}))
        elif remaining.days < EXPIRES_SOON_DAYS:
            warnings.append(CertWarning("warn.expires_soon", {"days": remaining.days}))
        if device_udid and not covers_device(
            record.devices, device_udid, record.all_devices
        ):
            warnings.append(CertWarning("warn.device_missing", {}))
        if not record.has_push:
            warnings.append(CertWarning("warn.no_push", {}))
        if bundle_id and not app_id_matches(record.app_id, bundle_id):
            warnings.append(
                CertWarning(
                    "warn.app_id_mismatch",
                    {"app_id": record.app_id, "bundle_id": bundle_id},
                )
            )
        return warnings

    def _folder(self, id: str) -> Path:
        folder = self._root / id
        if not _ID_RE.fullmatch(id) or not folder.is_dir():
            raise WispError("error.cert_not_found")
        return folder

    @staticmethod
    def _load_meta(folder: Path) -> dict:
        try:
            meta = json.loads((folder / _META_FILE).read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError, RecursionError):
            raise WispError("error.cert_meta_corrupt") from None
        if not isinstance(meta, dict):
            raise WispError("error.cert_meta_corrupt")
        if "all_devices" not in meta:
            try:
                meta["all_devices"] = parse_profile(
                    (folder / _PROFILE_FILE).read_bytes()
                ).all_devices
            except (OSError, WispError):
                raise WispError("error.cert_meta_corrupt") from None
        return meta
