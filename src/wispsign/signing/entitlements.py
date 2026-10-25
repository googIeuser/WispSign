"""Read zsign's embedded XML entitlements in every Mach-O architecture.

This checks the declared app identity and push environment against the profile;
it does not replace the device's cryptographic or provisioning checks.
"""

import os
import plistlib
import struct
from pathlib import Path
from typing import BinaryIO
from xml.parsers.expat import ExpatError

from wispsign.certs.profile import ProfileInfo
from wispsign.certs.store import app_id_matches
from wispsign.errors import WispError
from wispsign.signing.ipa import long_path

_THIN = {
    b"\xce\xfa\xed\xfe": ("<", 28),
    b"\xfe\xed\xfa\xce": (">", 28),
    b"\xcf\xfa\xed\xfe": ("<", 32),
    b"\xfe\xed\xfa\xcf": (">", 32),
}
_FAT = {
    b"\xca\xfe\xba\xbe": (">", 20),
    b"\xbe\xba\xfe\xca": ("<", 20),
    b"\xca\xfe\xba\xbf": (">", 32),
    b"\xbf\xba\xfe\xca": ("<", 32),
}
_MAX_REGION = 64 * 1024 * 1024


def _read(handle: BinaryIO, offset: int, size: int, end: int) -> bytes:
    if offset < 0 or size < 0 or size > min(end - offset, _MAX_REGION):
        raise ValueError("Mach-O range outside its container")
    handle.seek(offset)
    data = handle.read(size)
    if len(data) != size:
        raise ValueError("truncated Mach-O")
    return data


def _xml_entitlements(signature: bytes) -> dict:
    magic, length, count = struct.unpack_from(">III", signature)
    table_end = 12 + count * 8
    if magic != 0xFADE0CC0 or not table_end <= length <= len(signature):
        raise ValueError("invalid code signature")
    result = None
    for index in range(count):
        slot, offset = struct.unpack_from(">II", signature, 12 + index * 8)
        if slot != 5:
            continue
        if result is not None or not table_end <= offset <= length - 8:
            raise ValueError("invalid entitlements slot")
        blob_magic, size = struct.unpack_from(">II", signature, offset)
        if blob_magic != 0xFADE7171 or not 8 <= size <= length - offset:
            raise ValueError("invalid entitlements blob")
        result = plistlib.loads(signature[offset + 8 : offset + size])
        if not isinstance(result, dict):
            raise TypeError("entitlements are not a dictionary")
    if result is None:
        raise ValueError("missing XML entitlements")
    return result


def _thin_entitlements(handle: BinaryIO, start: int, size: int) -> dict:
    end = start + size
    header = _read(handle, start, 28, end)
    endian, header_size = _THIN[header[:4]]
    count, commands_size = struct.unpack_from(endian + "II", header, 16)
    commands = _read(handle, start + header_size, commands_size, end)
    if not 0 < count <= len(commands) // 8:
        raise ValueError("invalid load command count")
    cursor = 0
    signature = None
    for _ in range(count):
        command, command_size = struct.unpack_from(endian + "II", commands, cursor)
        if not 8 <= command_size <= len(commands) - cursor:
            raise ValueError("invalid load command size")
        if command == 0x1D:  # LC_CODE_SIGNATURE; offsets are relative to this slice
            if signature is not None or command_size != 16:
                raise ValueError("invalid code signature command")
            offset, length = struct.unpack_from(endian + "II", commands, cursor + 8)
            if offset < header_size + commands_size:
                raise ValueError("code signature overlaps load commands")
            signature = _read(handle, start + offset, length, end)
        cursor += command_size
    if signature is None:
        raise ValueError("missing code signature")
    return _xml_entitlements(signature)


def read_entitlements(executable: Path) -> tuple[dict, ...]:
    """Return the signed XML dictionary of every thin/universal Mach-O slice."""
    try:
        with open(long_path(executable), "rb") as handle:
            end = os.fstat(handle.fileno()).st_size
            header = _read(handle, 0, 8, end)
            if header[:4] in _THIN:
                return (_thin_entitlements(handle, 0, end),)
            endian, stride = _FAT[header[:4]]
            count = struct.unpack_from(endian + "I", header, 4)[0]
            if count == 0:
                raise ValueError("empty universal executable")
            table = _read(handle, 8, count * stride, end)
            results = []
            for index in range(count):
                offset, size = struct.unpack_from(
                    endian + ("II" if stride == 20 else "QQ"),
                    table,
                    index * stride + 8,
                )
                if offset < 8 + len(table) or size < 28 or size > end - offset:
                    raise ValueError("universal slice outside its container")
                results.append(_thin_entitlements(handle, offset, size))
            return tuple(results)
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        struct.error,
        plistlib.InvalidFileException,
        ExpatError,
    ) as exc:
        raise WispError("error.entitlements_invalid", str(exc)) from None


def verify_entitlements(app: Path, profile: ProfileInfo) -> None:
    """Reject missing or changed identity/push entitlements before packaging."""
    try:
        with open(long_path(app / "Info.plist"), "rb") as handle:
            info = plistlib.loads(handle.read(8 * 1024 * 1024))
        executable = info["CFBundleExecutable"]
        bundle_id = info["CFBundleIdentifier"]
        if (
            not isinstance(executable, str)
            or not executable
            or executable in (".", "..")
            or any(c in executable for c in "/\\:\0")
            or not isinstance(bundle_id, str)
        ):
            raise ValueError("invalid bundle executable or identifier")
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        plistlib.InvalidFileException,
        ExpatError,
    ) as exc:
        raise WispError("error.entitlements_invalid", str(exc)) from None
    expected_ids = {
        f"{profile.team_id}.{bundle_id}",
        f"{profile.team_id}.{profile.app_id}",
    }
    expected_push = profile.entitlements.get("aps-environment")
    for signed in read_entitlements(app / executable):
        identity = signed.get("application-identifier")
        if (
            not app_id_matches(profile.app_id, bundle_id)
            or not isinstance(identity, str)
            or identity not in expected_ids
            or signed.get("aps-environment") != expected_push
        ):
            raise WispError(
                "error.entitlements_invalid",
                "signed identity or push environment differs from the profile",
            )
