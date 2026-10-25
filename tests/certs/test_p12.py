import pytest
from certgen import make_pair

from wispsign.certs.p12 import load_p12
from wispsign.certs.profile import parse_profile
from wispsign.errors import WispError


def test_load_p12_ok():
    p12, prof, pw = make_pair()
    assert load_p12(p12, pw).serial == parse_profile(prof).cert_serials[0]


def test_load_p12_fields():
    info = load_p12(*make_pair(team="ABCDE12345", expires_days=30)[::2])
    assert info.team_id == "ABCDE12345"
    assert "ABCDE12345" in info.common_name


def test_load_p12_wrong_password():
    with pytest.raises(WispError, match="p12_password"):
        load_p12(make_pair()[0], "wrong")


def test_load_p12_error_hides_password():
    with pytest.raises(WispError) as exc:
        load_p12(make_pair()[0], "s3cret-wrong")
    assert "s3cret-wrong" not in str(exc.value)


def test_load_p12_no_key():
    from certgen import make_cert_only_p12

    p12, pw = make_cert_only_p12()
    with pytest.raises(WispError, match="p12_no_key"):
        load_p12(p12, pw)


def test_pairs_have_distinct_serials():
    a = load_p12(*make_pair()[::2])
    b = load_p12(*make_pair()[::2])
    assert a.serial != b.serial


def test_load_p12_unsupported_algorithm(monkeypatch):
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography.hazmat.primitives.serialization import pkcs12

    def boom(*_a, **_k):
        raise UnsupportedAlgorithm("RC2 secret-pw")

    monkeypatch.setattr(pkcs12, "load_key_and_certificates", boom)
    with pytest.raises(WispError) as exc:
        load_p12(b"x", "secret-pw")
    assert exc.value.code == "error.p12_unsupported"
    assert "secret-pw" not in str(exc.value)
