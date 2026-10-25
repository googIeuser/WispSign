import os

from appgen import make_app

from wispsign.signing.ipa import long_path
from wispsign.signing.verify import verify_bundle

MAX_PATH = 260


def test_verify_detects_tamper(signed_app):
    assert verify_bundle(signed_app).ok
    (signed_app / "res.txt").write_bytes(b"x")
    r = verify_bundle(signed_app)
    assert not r.ok and "res.txt" in r.bad


def test_verify_counts_nested_bundles(signed_app):
    r = verify_bundle(signed_app)
    assert r.ok and r.bad == () and r.bundles_checked == 2


def test_verify_detects_missing_file(signed_app):
    (signed_app / "res.txt").unlink()
    r = verify_bundle(signed_app)
    assert not r.ok and "res.txt" in r.bad


def test_verify_detects_tamper_in_nested_bundle(signed_app):
    (signed_app / "PlugIns" / "Ext.appex" / "Ext").write_bytes(b"x")
    r = verify_bundle(signed_app)
    assert not r.ok and "PlugIns/Ext.appex/Ext" in r.bad


def test_verify_detects_unsealed_file(signed_app):
    (signed_app / "added.txt").write_bytes(b"new")
    r = verify_bundle(signed_app)
    assert not r.ok and "added.txt" in r.bad


def test_verify_ignores_omitted_files(signed_app):
    (signed_app / "sub").mkdir()
    (signed_app / "sub" / ".DS_Store").write_bytes(b"finder")
    assert verify_bundle(signed_app).ok


def test_verify_unsigned_app_is_not_ok(tmp_path):
    r = verify_bundle(make_app(tmp_path / "u"))
    assert not r.ok and r.bundles_checked == 0


def test_verify_catches_unsealed_deep_file_after_long_path_signing(
    tmp_path, sign_in_place
):
    # zsign cannot list a directory deeper than MAX_PATH, silently leaves the file
    # out of CodeResources and still reports success.
    app = sign_in_place(make_app(tmp_path / "long", deep_path_len=300))
    r = verify_bundle(app)
    assert not r.ok and any(b.endswith("/deep.bin") for b in r.bad)


def test_verify_catches_wrong_hash_after_long_path_signing(tmp_path, sign_in_place):
    # A file whose directory fits MAX_PATH but whose own path does not gets a
    # wrong hash2 from zsign (the 0xe8008017 install failure).
    app = make_app(tmp_path / "long")
    base = os.path.abspath(app)
    directory = os.path.join(base, "a" * (MAX_PATH - 20 - len(base) - 1))
    os.makedirs(long_path(directory))
    target = os.path.join(directory, "f" * 40 + ".bin")
    assert len(directory) < MAX_PATH < len(target)
    with open(long_path(target), "wb") as handle:
        handle.write(b"long name")
    r = verify_bundle(sign_in_place(app))
    rel = os.path.relpath(target, base).replace(os.sep, "/")
    assert not r.ok and rel in r.bad
