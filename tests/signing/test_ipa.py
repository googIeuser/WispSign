import os
import stat
import zipfile
from pathlib import Path

import pytest
from appgen import make_app, make_ipa

from wispsign.errors import ERROR_CODES, WispError
from wispsign.signing.ipa import long_path, pack_ipa, safe_extract


def _zip(path: Path, members: dict[str, bytes], symlinks: tuple[str, ...] = ()) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name)
            if name in symlinks:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, data)
    return path


def _assert_invalid(ipa: Path, dest: Path, **kwargs: int) -> None:
    with pytest.raises(WispError) as err:
        safe_extract(ipa, dest, **kwargs)
    assert err.value.code == "error.ipa_invalid"
    assert str(dest.parent) not in str(err.value)


def test_error_code_registered():
    assert "error.ipa_invalid" in ERROR_CODES


def test_extract_roundtrip(tmp_path):
    app = safe_extract(make_ipa(tmp_path), tmp_path / "w")
    assert app.name.endswith(".app")
    assert (app / "res.txt").read_bytes() == b"resource"
    assert (app / "PlugIns/Ext.appex/Info.plist").is_file()


def test_extract_rejects_traversal(tmp_path):
    ipa = _zip(
        tmp_path / "a.ipa",
        {"Payload/A.app/Info.plist": b"x", "Payload/../../evil.txt": b"evil"},
    )
    dest = tmp_path / "sub" / "w"
    _assert_invalid(ipa, dest)
    assert not (tmp_path / "evil.txt").exists()
    assert not dest.exists()


def test_extract_rejects_backslash_traversal(tmp_path):
    ipa = _zip(
        tmp_path / "a.ipa", {"Payload\\..\\..\\evil.txt": b"e", "Payload/A.app/x": b"x"}
    )
    _assert_invalid(ipa, tmp_path / "w")


@pytest.mark.parametrize("name", ["/abs/evil.txt", "C:/evil.txt", "\\evil.txt"])
def test_extract_rejects_absolute(tmp_path, name):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x", name: b"e"})
    _assert_invalid(ipa, tmp_path / "w")


def test_extract_rejects_symlink(tmp_path):
    ipa = _zip(
        tmp_path / "a.ipa",
        {"Payload/A.app/Info.plist": b"x", "Payload/A.app/link": b"/etc"},
        symlinks=("Payload/A.app/link",),
    )
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest)
    assert not dest.exists()


def test_extract_requires_payload_app(tmp_path):
    ipa = _zip(tmp_path / "a.ipa", {"Other/A.app/x": b"x"})
    _assert_invalid(ipa, tmp_path / "w")


def test_extract_rejects_two_apps(tmp_path):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x", "Payload/B.app/x": b"x"})
    _assert_invalid(ipa, tmp_path / "w")


def test_extract_rejects_non_zip(tmp_path):
    bad = tmp_path / "a.ipa"
    bad.write_bytes(b"not a zip")
    _assert_invalid(bad, tmp_path / "w")


def test_extract_size_limit_and_cleanup(tmp_path):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x" * 100})
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest, max_total=50)
    assert not dest.exists()


def test_failure_keeps_preexisting_dest_clean(tmp_path):
    dest = tmp_path / "w"
    dest.mkdir()
    (dest / "keep.txt").write_text("k")
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x" * 100})
    _assert_invalid(ipa, dest, max_total=50)
    assert [p.name for p in dest.iterdir()] == ["keep.txt"]


def test_extract_cleans_up_on_corrupt_member(tmp_path):
    ipa = _zip(
        tmp_path / "a.ipa",
        {"Payload/A.app/a": b"a" * 40, "Payload/A.app/b": b"b" * 40},
    )
    raw = bytearray(ipa.read_bytes())
    raw[raw.rfind(b"b" * 40)] ^= 0xFF
    ipa.write_bytes(raw)
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest)
    assert not dest.exists()


def test_deep_paths_roundtrip(tmp_path):
    ipa = make_ipa(tmp_path, deep_path_len=300)
    app = safe_extract(ipa, tmp_path / "w")
    deep = [
        os.path.join(root, f)
        for root, _, files in os.walk(long_path(app))
        for f in files
        if f == "deep.bin"
    ]
    assert len(deep) == 1
    assert len(deep[0].removeprefix("\\\\?\\")) > 260


def test_pack_ipa_layout_and_exec_bit(tmp_path):
    app = make_app(tmp_path)
    out = pack_ipa(app, tmp_path / "o.ipa")
    with zipfile.ZipFile(out) as archive:
        names = set(archive.namelist())
        assert "Payload/Test.app/Info.plist" in names
        assert "Payload/Test.app/PlugIns/Ext.appex/Ext" in names
        files = [i for i in archive.infolist() if not i.is_dir()]
        assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in files)
        assert (archive.getinfo("Payload/Test.app/Test").external_attr >> 16) & 0o111
        assert (
            not (archive.getinfo("Payload/Test.app/res.txt").external_attr >> 16)
            & 0o111
        )


@pytest.mark.parametrize(
    "name",
    [
        "Payload/A.app/a*b",
        'Payload/A.app/a"b',
        "Payload/A.app/a\x01b",
        "Payload/A.app/a?",
    ],
)
def test_extract_rejects_invalid_windows_chars(tmp_path, name):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x", name: b"e"})
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest)
    assert not dest.exists()


@pytest.mark.parametrize(
    "name", ["Payload/A.app/x ", "Payload/A.app/x.", "Payload/A.app /x"]
)
def test_extract_rejects_trailing_space_or_dot(tmp_path, name):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/y": b"y", name: b"e"})
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest)
    assert not dest.exists()


def test_extract_rejects_file_then_dir_collision(tmp_path):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x", "Payload/A.app/x/y": b"y"})
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest)
    assert not dest.exists()


def test_extract_rejects_payload_as_file(tmp_path):
    ipa = _zip(tmp_path / "a.ipa", {"Payload": b"p", "Payload/A.app/x": b"x"})
    dest = tmp_path / "w"
    _assert_invalid(ipa, dest)
    assert not dest.exists()


def test_extract_wraps_write_oserror(tmp_path):
    ipa = _zip(tmp_path / "a.ipa", {"Payload/A.app/x": b"x"})
    dest = tmp_path / "w"
    dest.mkdir()
    (dest / "Payload").write_bytes(b"blocker")
    with pytest.raises(WispError) as err:
        safe_extract(ipa, dest)
    assert err.value.code == "error.ipa_invalid"
    assert str(tmp_path) not in str(err.value)
    assert (dest / "Payload").read_bytes() == b"blocker"
