import pytest

from wispsign.errors import WispError
from wispsign.secrets import protect, unprotect


def test_dpapi_roundtrip():
    blob = protect("sample-pass-123")
    assert "sample-pass-123" not in blob
    assert unprotect(blob) == "sample-pass-123"


def test_dpapi_roundtrip_unicode_and_empty():
    assert unprotect(protect("şifre-ğüı")) == "şifre-ğüı"
    assert unprotect(protect("")) == ""


def test_unprotect_garbage_raises():
    with pytest.raises(WispError) as ei:
        unprotect("bm90LWEtYmxvYg==")
    assert ei.value.code == "error.secret_unreadable"


def test_unprotect_invalid_base64_raises():
    with pytest.raises(WispError) as ei:
        unprotect("!!!not base64!!!")
    assert ei.value.code == "error.secret_unreadable"
