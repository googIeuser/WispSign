import re
from pathlib import Path

from wispsign.paths import AppPaths, make_work_dir


def test_app_paths_layout(tmp_path):
    p = AppPaths(tmp_path)
    assert p.settings == tmp_path / "settings.json"
    assert p.repos == tmp_path / "repos.json"
    assert p.library == tmp_path / "library.json"
    assert p.certs == tmp_path / "certs"
    assert p.ipas == tmp_path / "ipas"
    assert p.cache == tmp_path / "cache"


def test_ensure_creates_directories_and_is_idempotent(tmp_path):
    p = AppPaths(tmp_path / "root")
    p.ensure()
    p.ensure()
    assert p.certs.is_dir() and p.ipas.is_dir() and p.cache.is_dir()


def test_tmp_paths_fixture_is_ensured(tmp_paths):
    assert tmp_paths.certs.is_dir()


def test_default_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert AppPaths.default().root == tmp_path / "WispSign"


def test_work_dir_is_short_and_unique(tmp_path):
    a, b = make_work_dir(tmp_path), make_work_dir(tmp_path)
    assert a != b and a.is_dir() and len(a.name) == 4
    assert re.fullmatch(r"[a-z0-9]{4}", a.name)


def test_work_dir_defaults_to_localappdata_ws(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    d = make_work_dir()
    assert d.parent == tmp_path / "WS" and d.is_dir()


def test_work_dir_retries_on_collision(monkeypatch, tmp_path):
    (tmp_path / "aaaa").mkdir()
    names = iter(["aaaa", "bbbb"])
    monkeypatch.setattr("wispsign.paths._random_name", lambda: next(names))
    assert make_work_dir(tmp_path) == Path(tmp_path / "bbbb")
