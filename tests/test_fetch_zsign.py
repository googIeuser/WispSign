import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "fetch_zsign.py"


@pytest.fixture
def fetch(monkeypatch, tmp_path):
    pass
    spec = importlib.util.spec_from_file_location("fetch_zsign", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vendor = tmp_path / "vendor" / "zsign"
    monkeypatch.setattr(module, "VENDOR", vendor)
    monkeypatch.setattr(module, "ZIP_PATH", vendor / "zsign-windows-x64.zip")
    monkeypatch.setattr(module, "EXE_PATH", vendor / "zsign.exe")
    return module


def _zip(exe: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("zsign.exe", exe)
    return buffer.getvalue()


def test_hash_mismatch_returns_1_and_writes_nothing(fetch, monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "_download", lambda: _zip(b"tampered"))
    assert fetch.main() == 1
    assert list(tmp_path.iterdir()) == []


def test_extracts_the_verified_bytes(fetch, monkeypatch, capsys):
    data = _zip(b"MZ verified")
    monkeypatch.setattr(fetch, "_download", lambda: data)
    monkeypatch.setattr(fetch, "SHA256", hashlib.sha256(data).hexdigest())
    assert fetch.main() == 0
    assert fetch.EXE_PATH.read_bytes() == b"MZ verified"
    assert fetch.ZIP_PATH.read_bytes() == data
    assert capsys.readouterr().out.startswith("zsign OK ")


def test_rerun_reuses_cached_zip(fetch, monkeypatch):
    data = _zip(b"MZ cached")
    monkeypatch.setattr(fetch, "_download", lambda: data)
    monkeypatch.setattr(fetch, "SHA256", hashlib.sha256(data).hexdigest())
    assert fetch.main() == 0

    def offline() -> bytes:
        raise AssertionError("should not download again")

    monkeypatch.setattr(fetch, "_download", offline)
    assert fetch.main() == 0
    assert fetch.EXE_PATH.read_bytes() == b"MZ cached"
