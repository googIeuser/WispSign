from datetime import datetime

import pytest
from certgen import make_pair, valid_plist, wrap_plist

from wispsign.certs.profile import parse_profile
from wispsign.errors import WispError


def test_parse_profile_explicit_push():
    _, prof, _ = make_pair(app_id="com.example.demo", push=True)
    info = parse_profile(prof)
    assert info.app_id == "com.example.demo"
    assert not info.is_wildcard
    assert info.has_push
    assert info.team_id == "TEAM123456"


def test_parse_profile_wildcard():
    info = parse_profile(make_pair(app_id="com.example.*")[1])
    assert info.is_wildcard
    assert not info.has_push


def test_parse_profile_fields():
    info = parse_profile(make_pair(devices=("A", "B"))[1])
    assert info.devices == ("A", "B")
    assert info.app_groups == ()
    assert isinstance(info.expires, datetime)
    assert len(info.cert_serials) == 1
    assert info.cert_serials[0] == info.cert_serials[0].upper()


def test_parse_profile_no_devices():
    assert parse_profile(make_pair(devices=())[1]).devices == ()


@pytest.mark.parametrize("all_devices", [False, True])
def test_profile_records_explicit_all_devices_permission(all_devices):
    profile = wrap_plist(valid_plist(ProvisionsAllDevices=all_devices))
    assert parse_profile(profile).all_devices is all_devices


def test_parse_profile_garbage():
    with pytest.raises(WispError, match="profile_invalid"):
        parse_profile(b"nope")


def test_parse_profile_bad_plist():
    with pytest.raises(WispError, match="profile_invalid"):
        parse_profile(b"<?xml version='1.0'?><plist><dict></plist>")


def _ent(app_id, **extra):
    return {"application-identifier": app_id, **extra}


@pytest.mark.parametrize(
    "overrides",
    [
        {"Name": None},
        {"UUID": None},
        {"Entitlements": None},
        {"ExpirationDate": None},
        {"TeamIdentifier": None},
        {"TeamIdentifier": []},
        {"TeamIdentifier": "TEAM123456"},
        {"Name": 5},
        {"ProvisionedDevices": "ABCDEF"},
        {"ProvisionsAllDevices": "true"},
        {"ProvisionsAllDevices": 1},
        {"DeveloperCertificates": [b"not der"]},
        {"DeveloperCertificates": "x"},
        {"Entitlements": {}},
        {"Entitlements": _ent("com.a.b")},
        {"Entitlements": _ent("OTHER.com.a.b")},
        {"Entitlements": _ent("TEAM123456.")},
        {
            "Entitlements": _ent(
                "TEAM123456.com.a", **{"com.apple.security.application-groups": "g"}
            )
        },
        {"Entitlements": _ent(5)},
    ],
)
def test_parse_profile_rejects_malformed(overrides):
    with pytest.raises(WispError, match="profile_invalid"):
        parse_profile(wrap_plist(valid_plist(**overrides)))


def test_parse_profile_minimal_valid():
    info = parse_profile(wrap_plist(valid_plist()))
    assert info.app_id == "com.a.b"
    assert info.devices == () and info.cert_serials == ()
