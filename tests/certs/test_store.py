import json
from datetime import UTC, datetime, timedelta

import pytest
from certgen import make_pair
from cryptography import x509

from wispsign.certs.store import (
    EXPIRES_SOON_DAYS,
    WARN_CODES,
    CertStore,
    CertWarning,
)
from wispsign.errors import WispError


def test_import_and_list(tmp_paths):
    p12, prof, pw = make_pair(app_id="com.example.demo", push=True)
    rec = CertStore(tmp_paths).import_pair(p12, prof, pw, "Demo App")
    assert CertStore(tmp_paths).list() == [rec] and rec.has_push
    assert rec.app_id == "com.example.demo" and rec.nickname == "Demo App"
    meta = (tmp_paths.certs / rec.id / "meta.json").read_text()
    assert pw not in meta and "password_dpapi" in meta
    assert json.loads(meta)["expires"].endswith("Z")


def test_import_rejects_mismatched_pair(tmp_paths):
    p12_a, _, pw = make_pair()
    _, prof_b, _ = make_pair()
    with pytest.raises(WispError, match="cert_profile_mismatch"):
        CertStore(tmp_paths).import_pair(p12_a, prof_b, pw, "x")
    assert list(tmp_paths.certs.iterdir()) == []


def test_import_rejects_different_certificates_with_the_same_serial(
    tmp_paths, monkeypatch
):
    monkeypatch.setattr(x509, "random_serial_number", lambda: 123456789)
    p12, _, password = make_pair()
    _, other_profile, _ = make_pair()
    with pytest.raises(WispError, match="cert_profile_mismatch"):
        CertStore(tmp_paths).import_pair(p12, other_profile, password, "Demo")
    assert list(tmp_paths.certs.iterdir()) == []


def test_import_wrong_password(tmp_paths):
    p12, prof, _ = make_pair()
    with pytest.raises(WispError, match="p12_password"):
        CertStore(tmp_paths).import_pair(p12, prof, "wrong", "x")
    assert list(tmp_paths.certs.iterdir()) == []


@pytest.mark.parametrize("all_devices", [False, True])
@pytest.mark.parametrize("legacy", [False, True])
def test_validate_requires_explicit_all_devices_permission(
    tmp_paths, all_devices, legacy
):
    p12, profile, password = make_pair(devices=(), push=True, all_devices=all_devices)
    store = CertStore(tmp_paths)
    record = store.import_pair(p12, profile, password, "Demo")
    meta_path = tmp_paths.certs / record.id / "meta.json"
    if legacy:
        meta = json.loads(meta_path.read_text())
        del meta["all_devices"]
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    before = meta_path.read_bytes()
    assert store.list()[0].all_devices is all_devices
    expected = [] if all_devices else [CertWarning("warn.device_missing", {})]
    assert store.validate(record.id, "UNLISTED", datetime.now(UTC)) == expected
    assert meta_path.read_bytes() == before


def test_validate_flags_expired_and_missing_device(tmp_paths):
    p12, prof, pw = make_pair(devices=("AAA",), expires_days=3)
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    warnings = s.validate(rec.id, "BBB", datetime.now(UTC))
    assert {w.code for w in warnings} == {
        "warn.expires_soon",
        "warn.device_missing",
        "warn.no_push",
    }
    assert next(w for w in warnings if w.code == "warn.expires_soon").params[
        "days"
    ] in (2, 3)
    later = datetime.now(UTC) + timedelta(days=4)
    codes = {w.code for w in s.validate(rec.id, "AAA", later)}
    assert "warn.expired" in codes and "warn.expires_soon" not in codes
    assert codes <= set(WARN_CODES)


def test_validate_clean_cert_has_no_warnings(tmp_paths):
    p12, prof, pw = make_pair(devices=("AAA",), push=True)
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    assert s.validate(rec.id, "AAA", datetime.now(UTC)) == []
    assert s.validate(rec.id, None, datetime.now(UTC)) == []


def test_materialize_returns_plain_password(tmp_paths):
    p12, prof, pw = make_pair()
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    p12_path, prof_path, password = s.materialize(rec.id)
    assert password == pw
    assert p12_path.read_bytes() == p12 and prof_path.read_bytes() == prof


def test_remove_and_unknown_id(tmp_paths):
    p12, prof, pw = make_pair()
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    s.remove(rec.id)
    assert s.list() == []
    for call in (
        s.remove,
        s.materialize,
        lambda i: s.validate(i, None, datetime.now(UTC)),
    ):
        with pytest.raises(WispError, match="cert_not_found"):
            call(rec.id)
    with pytest.raises(WispError, match="cert_not_found"):
        s.remove("../x")


def test_list_skips_corrupt_and_tmp_folders(tmp_paths):
    p12, prof, pw = make_pair()
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    (tmp_paths.certs / "nometa").mkdir()
    bad = tmp_paths.certs / "badmeta"
    bad.mkdir()
    (bad / "meta.json").write_text("{not json", encoding="utf-8")
    partial = tmp_paths.certs / "partial"
    partial.mkdir()
    (partial / "meta.json").write_text('{"id": "partial"}', encoding="utf-8")
    (tmp_paths.certs / ".tmp-abc").mkdir()
    assert s.list() == [rec]


def test_validate_compares_udids_case_insensitively(tmp_paths):
    p12, prof, pw = make_pair(devices=("00008110-000a1b2c3d4e5f60",), push=True)
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    assert s.validate(rec.id, "00008110-000A1B2C3D4E5F60", datetime.now(UTC)) == []


def test_validate_empty_device_list_does_not_cover_every_device(tmp_paths):
    p12, prof, pw = make_pair(devices=(), push=True)
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    assert rec.devices == ()
    assert s.validate(rec.id, "ANY-UDID", datetime.now(UTC)) == [
        CertWarning("warn.device_missing", {})
    ]


def test_expires_soon_starts_below_fourteen_whole_days(tmp_paths):
    p12, prof, pw = make_pair(devices=("AAA",), push=True)
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    edge = rec.expires - timedelta(days=EXPIRES_SOON_DAYS)
    assert s.validate(rec.id, "AAA", edge) == []
    (warning,) = s.validate(rec.id, "AAA", edge + timedelta(seconds=1))
    assert (warning.code, warning.params) == ("warn.expires_soon", {"days": 13})
    (expired,) = s.validate(rec.id, "AAA", rec.expires)
    assert expired.code == "warn.expired"


BROKEN_META = [
    b"{not json",
    b"\xff\xfe\x00garbage",
    b'{"id": "partial"}',
    b"[1, 2]",
]


@pytest.mark.parametrize("raw", [*BROKEN_META, None])
def test_list_reports_broken_cert_without_touching_it(tmp_paths, raw):
    p12, prof, pw = make_pair()
    s = CertStore(tmp_paths)
    good = s.import_pair(p12, prof, pw, "x")
    folder = tmp_paths.certs / "0123456789ab"
    folder.mkdir()
    if raw is not None:
        (folder / "meta.json").write_bytes(raw)
    listed = s.list()
    assert good in listed and good.broken is False
    (broken,) = [r for r in listed if r.broken]
    assert broken.id == "0123456789ab"
    if raw is not None:  # never renamed aside: the user decides
        assert (folder / "meta.json").read_bytes() == raw
    assert not list(folder.glob("meta.json.corrupt-*"))
    s.remove(broken.id)
    assert not folder.exists()
    assert s.list() == [good]


def test_broken_cert_cannot_be_used(tmp_paths):
    folder = tmp_paths.certs / "0123456789ab"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_bytes(b"{not json")
    s = CertStore(tmp_paths)
    for call in (s.materialize, lambda i: s.validate(i, None, datetime.now(UTC))):
        with pytest.raises(WispError, match="cert_meta_corrupt"):
            call("0123456789ab")


@pytest.mark.parametrize(
    "app_id,bundle_id,warned",
    [
        ("com.example.demo", "com.example.demo", False),
        ("com.example.demo", "com.example.other", True),
        ("com.example.*", "com.example.demo", False),
        ("com.example.*", "org.example.demo", True),
        ("*", "org.example.demo", False),
    ],
)
def test_validate_warns_when_app_id_does_not_match(
    tmp_paths, app_id, bundle_id, warned
):
    p12, prof, pw = make_pair(app_id=app_id, devices=("AAA",), push=True)
    s = CertStore(tmp_paths)
    rec = s.import_pair(p12, prof, pw, "x")
    warnings = s.validate(rec.id, "AAA", datetime.now(UTC), bundle_id)
    expected = (
        [
            CertWarning(
                "warn.app_id_mismatch", {"app_id": app_id, "bundle_id": bundle_id}
            )
        ]
        if warned
        else []
    )
    assert warnings == expected
    assert s.validate(rec.id, "AAA", datetime.now(UTC)) == []  # no bundle: no check
    assert "warn.app_id_mismatch" in WARN_CODES
