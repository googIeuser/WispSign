"""Download the pinned zsign release into vendor/zsign/zsign.exe.

The release zip is verified against a pinned SHA-256 before anything is
extracted; a mismatch exits with status 1. Re-running is cheap: a cached zip
with the right hash is reused and an up-to-date zsign.exe is left alone.
"""

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://github.com/zhlynn/zsign/releases/download/v1.1.2/zsign-windows-x64.zip"
SHA256 = "96b5bf7029a52c67cdb78b68b3666d8ff1e31e5c435535964be2a482afc09e5c"
TIMEOUT_S = 60
EXE_NAME = "zsign.exe"

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "zsign"
ZIP_PATH = VENDOR / "zsign-windows-x64.zip"
EXE_PATH = VENDOR / EXE_NAME


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download() -> bytes:
    with urllib.request.urlopen(URL, timeout=TIMEOUT_S) as response:
        return response.read()


def _archive_bytes() -> bytes:
    if ZIP_PATH.is_file():
        cached = ZIP_PATH.read_bytes()
        if _sha256(cached) == SHA256:
            return cached
    return _download()


def _extract_exe(data: bytes) -> bytes:
    """Read zsign.exe from the already-verified bytes, never from disk again."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read(EXE_NAME)


def main() -> int:
    data = _archive_bytes()
    digest = _sha256(data)
    if digest != SHA256:
        print(f"zsign SHA-256 mismatch: expected {SHA256}, got {digest}")
        return 1
    exe = _extract_exe(data)
    VENDOR.mkdir(parents=True, exist_ok=True)
    if not ZIP_PATH.is_file() or ZIP_PATH.read_bytes() != data:
        ZIP_PATH.write_bytes(data)
    if not EXE_PATH.is_file() or EXE_PATH.read_bytes() != exe:
        EXE_PATH.write_bytes(exe)
    print(f"zsign OK {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
