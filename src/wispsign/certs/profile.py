"""Parse .mobileprovision files (CMS SignedData wrapping an XML plist)."""

import plistlib
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.parsers.expat import ExpatError

from cryptography import x509
from cryptography.hazmat.primitives import hashes

from wispsign.errors import WispError


@dataclass(frozen=True)
class ProfileInfo:
    name: str
    uuid: str
    team_id: str
    app_id: str  # excludes the team prefix
    is_wildcard: bool
    has_push: bool
    app_groups: tuple[str, ...]
    devices: tuple[str, ...]
    cert_serials: tuple[str, ...]
    expires: datetime
    entitlements: dict
    cert_fingerprints: tuple[str, ...] = ()
    all_devices: bool = False


def _invalid() -> WispError:
    return WispError("error.profile_invalid")


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise _invalid()
    return value


def _str_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _invalid()
    return tuple(value)


def _load_plist(data: bytes) -> dict:
    start = data.find(b"<?xml")
    end = data.rfind(b"</plist>")
    if start < 0 or end < start:
        raise _invalid()
    try:
        plist = plistlib.loads(data[start : end + len(b"</plist>")])
    except (ValueError, plistlib.InvalidFileException, ExpatError) as exc:
        raise _invalid() from exc
    if not isinstance(plist, dict):
        raise _invalid()
    return plist


def _certificates(certs: object) -> tuple[x509.Certificate, ...]:
    if not isinstance(certs, list) or not all(isinstance(c, bytes) for c in certs):
        raise _invalid()
    try:
        return tuple(x509.load_der_x509_certificate(c) for c in certs)
    except ValueError as exc:
        raise _invalid() from exc


def parse_profile(data: bytes) -> ProfileInfo:
    plist = _load_plist(data)
    try:
        raw_entitlements = plist["Entitlements"]
        raw_expires = plist["ExpirationDate"]
        raw_teams = plist["TeamIdentifier"]
        name = _str(plist["Name"])
        uuid = _str(plist["UUID"])
    except KeyError as exc:
        raise _invalid() from exc
    if not isinstance(raw_entitlements, dict) or not isinstance(raw_expires, datetime):
        raise _invalid()
    teams = _str_list(raw_teams)
    if not teams:
        raise _invalid()
    team_id = teams[0]
    full_app_id = _str(raw_entitlements.get("application-identifier"))
    prefix = f"{team_id}."
    app_id = full_app_id[len(prefix) :]
    if not full_app_id.startswith(prefix) or not app_id:
        raise _invalid()
    expires = raw_expires
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    all_devices = plist.get("ProvisionsAllDevices", False)
    if not isinstance(all_devices, bool):
        raise _invalid()
    certificates = _certificates(plist.get("DeveloperCertificates", []))
    return ProfileInfo(
        name=name,
        uuid=uuid,
        team_id=team_id,
        app_id=app_id,
        is_wildcard=app_id.endswith("*"),
        has_push="aps-environment" in raw_entitlements,
        app_groups=_str_list(
            raw_entitlements.get("com.apple.security.application-groups", [])
        ),
        devices=_str_list(plist.get("ProvisionedDevices", [])),
        cert_serials=tuple(format(c.serial_number, "X") for c in certificates),
        expires=expires,
        entitlements=dict(raw_entitlements),
        cert_fingerprints=tuple(
            c.fingerprint(hashes.SHA256()).hex() for c in certificates
        ),
        all_devices=all_devices,
    )
