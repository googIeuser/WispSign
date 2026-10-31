pass

import base64
import binascii
import ctypes
from ctypes import wintypes

from wispsign.errors import WispError


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
_kernel32.LocalFree.restype = wintypes.HLOCAL
for _fn in (_crypt32.CryptProtectData, _crypt32.CryptUnprotectData):
    _fn.restype = wintypes.BOOL

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


def _blob_in(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buf = ctypes.create_string_buffer(data, max(len(data), 1))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _call(func, data: bytes) -> bytes | None:
    blob_in, _keepalive = _blob_in(data)
    blob_out = _DataBlob()
    ok = func(
        ctypes.byref(blob_in), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
    )
    if not ok:
        return None
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def protect(plain: str) -> str:
    out = _call(_crypt32.CryptProtectData, plain.encode("utf-8"))
    if out is None:
        raise WispError("error.secret_unreadable", "CryptProtectData failed")
    return base64.b64encode(out).decode("ascii")


def unprotect(blob: str) -> str:
    try:
        raw = base64.b64decode(blob, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WispError("error.secret_unreadable", "invalid base64") from exc
    out = _call(_crypt32.CryptUnprotectData, raw)
    if out is None:
        raise WispError("error.secret_unreadable", "CryptUnprotectData failed")
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WispError("error.secret_unreadable", "invalid utf-8") from exc
