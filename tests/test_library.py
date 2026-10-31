import json
import zipfile

import pytest
from appgen import PNG_1X1, make_ipa

from wispsign.errors import WispError
from wispsign.library import Library
from wispsign.repos.models import RepoApp


def _app(**over):
    base = dict(  # noqa: C408
        repo_url="https://r.example/repo.json",
        name="Remote",
        bundle_id="com.remote.app",
        version="2.0",
        download_url="https://r.example/a.ipa",
        icon_url=None,
        size=None,
        description="",
        developer=None,
    )
    return RepoApp(**{**base, **over})


@pytest.fixture
def library(tmp_paths):
    return Library(tmp_paths)


def test_add_file_reads_info(library, tmp_paths, tmp_path):
    ipa = make_ipa(tmp_path / "src")
    entry = library.add_file(ipa)
    assert (entry.name, entry.bundle_id, entry.version) == (
        "Test",
        "com.test.app",
        "1.0",
    )
    assert entry.source == "file"
    assert entry.added_at.endswith("Z")
    stored = tmp_paths.ipas / entry.path
    assert stored.is_file() and stored.read_bytes() == ipa.read_bytes()
    assert library.list() == [entry]
    assert json.loads(tmp_paths.library.read_text())[0]["bundle_id"] == "com.test.app"


def test_add_file_rejects_non_ipa(library, tmp_path):
    bad = tmp_path / "x.ipa"
    bad.write_bytes(b"not a zip")
    with pytest.raises(WispError) as exc:
        library.add_file(bad)
    assert exc.value.code == "error.ipa_invalid"
    assert library.list() == []


def test_add_file_rejects_zip_without_app(library, tmp_path):
    bad = tmp_path / "x.ipa"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(WispError) as exc:
        library.add_file(bad)
    assert exc.value.code == "error.ipa_invalid"


def test_add_file_rejects_missing_file(library, tmp_path):
    with pytest.raises(WispError) as exc:
        library.add_file(tmp_path / "nope.ipa")
    assert exc.value.code == "error.io"


def test_icon_returns_png_or_none(library, tmp_path):
    entry = library.add_file(make_ipa(tmp_path / "src"))
    assert library.icon(entry.id) == PNG_1X1
    assert library.icon("unknown") is None


def test_add_download_uses_repo_metadata(library, tmp_paths, tmp_path):
    ipa = make_ipa(tmp_path / "dl")
    entry = library.add_download(_app(), ipa)
    assert (entry.name, entry.bundle_id, entry.version) == (
        "Remote",
        "com.remote.app",
        "2.0",
    )
    assert entry.source == "https://r.example/repo.json"
    assert (tmp_paths.ipas / entry.path).is_file()


def test_each_download_gets_its_own_entry(library, tmp_paths, tmp_path):
    made = make_ipa(tmp_path / "dl")
    one = tmp_paths.ipas / "com.remote.app-2.0.ipa"
    two = tmp_paths.ipas / "com.remote.app-2.0-2.ipa"
    one.write_bytes(made.read_bytes())
    two.write_bytes(made.read_bytes())
    first = library.add_download(_app(), one)
    second = library.add_download(_app(), two)
    assert first.id != second.id
    assert (first.path, second.path) == (one.name, two.name)
    assert first.owned and second.owned
    assert len(library.list()) == 2


def test_add_download_invalid_ipa_removed(library, tmp_paths):
    bad = tmp_paths.ipas / "bad.ipa"
    bad.write_bytes(b"junk")
    with pytest.raises(WispError):
        library.add_download(_app(), bad)
    assert not bad.exists()


def test_remove_deletes_file_and_entry(library, tmp_paths, tmp_path):
    entry = library.add_file(make_ipa(tmp_path / "src"))
    library.remove(entry.id)
    assert library.list() == []
    assert not (tmp_paths.ipas / entry.path).exists()
    assert library.icon(entry.id) is None
    library.remove(entry.id)


def test_get_unknown_raises(library):
    with pytest.raises(WispError) as exc:
        library.get("nope")
    assert exc.value.code == "error.entry_not_found"


def test_list_skips_malformed_rows(library, tmp_paths):
    tmp_paths.library.write_text(json.dumps([{"id": "x"}, 5]))
    assert library.list() == []


def test_add_download_elsewhere_registers_in_place(library, tmp_paths, tmp_path):
    ipa = make_ipa(tmp_path / "dl")
    entry = library.add_download(_app(), ipa)
    assert entry.path == str(ipa.resolve()) and entry.owned
    assert list(tmp_paths.ipas.iterdir()) == []


def test_remove_deletes_owned_download_outside_ipas(library, tmp_path):
    ipa = make_ipa(tmp_path / "dl")
    entry = library.add_download(_app(), ipa)
    library.remove(entry.id)
    assert not ipa.exists()


def test_add_file_copies_are_owned(library, tmp_path):
    source = make_ipa(tmp_path / "src")
    entry = library.add_file(source)
    assert entry.owned
    library.remove(entry.id)
    assert source.is_file()


def _legacy_row(path):
    return {
        "id": "legacy000001",
        "name": "Demo App",
        "bundle_id": "com.example.demo",
        "version": "1.0",
        "path": path,
        "source": "file",
        "added_at": "2026-10-24T12:00:00Z",
    }


def test_legacy_entry_with_outside_path_is_not_deleted(library, tmp_paths, tmp_path):
    user_file = make_ipa(tmp_path / "user")
    tmp_paths.library.write_text(json.dumps([_legacy_row(str(user_file))]))
    (entry,) = library.list()
    assert entry.owned is False
    library.remove(entry.id)
    assert library.list() == []
    assert user_file.is_file()


def test_legacy_entry_inside_ipas_is_owned(library, tmp_paths):
    stored = tmp_paths.ipas / "old.ipa"
    stored.write_bytes(b"x")
    tmp_paths.library.write_text(json.dumps([_legacy_row("old.ipa")]))
    (entry,) = library.list()
    assert entry.owned is True
    library.remove(entry.id)
    assert not stored.exists()


@pytest.mark.parametrize("value", ["false", "true", 1, None])
def test_only_a_real_true_marks_an_entry_as_owned(library, tmp_paths, value):
    user_file = tmp_paths.ipas / "user.ipa"
    user_file.write_bytes(b"x")
    row = {**_legacy_row("user.ipa"), "owned": value}
    tmp_paths.library.write_text(json.dumps([row]))
    (entry,) = library.list()
    assert entry.owned is False
    library.remove(entry.id)
    assert user_file.is_file()


def test_not_owned_entry_is_never_deleted(library, tmp_paths, tmp_path):
    user_file = tmp_paths.ipas / "user.ipa"
    user_file.write_bytes(b"x")
    row = {**_legacy_row("user.ipa"), "owned": False}
    tmp_paths.library.write_text(json.dumps([row]))
    library.remove("legacy000001")
    assert user_file.is_file()
