import _winapi
import json
import os
import time
from pathlib import Path

from wispsign import app
from wispsign.bridge.api import WispApi


class _Hooks:
    def __init__(self):
        self.items: list = []

    def __iadd__(self, item):
        self.items.append(item)
        return self


class FakeWindow:
    def __init__(self, fail: bool = False):
        self.scripts: list[str] = []
        self.fail = fail
        self.events = type("E", (), {"loaded": _Hooks(), "closed": _Hooks()})()

    def evaluate_js(self, script: str):
        if self.fail:
            raise RuntimeError("window is gone")
        self.scripts.append(script)


def test_main_wires_api_and_url(monkeypatch, tmp_path):
    created: dict = {}
    started: dict = {}
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(
        app.webview,
        "create_window",
        lambda *a, **k: created.update(a=a, k=k) or FakeWindow(),
    )
    monkeypatch.setattr(app.webview, "start", lambda *a, **k: started.update(k=k))

    assert app.main([]) == 0

    kwargs = created["k"]
    assert created["a"][0] == "WispSign"
    assert kwargs["url"].endswith("index.html")
    assert isinstance(kwargs["js_api"], WispApi)
    assert kwargs["background_color"] == "#0b0b0b"
    assert (kwargs["width"], kwargs["height"]) == (1280, 800)
    assert kwargs["min_size"] == (1024, 680)
    assert started["k"]["debug"] is False


def test_debug_flag_enables_devtools(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    started: dict = {}
    monkeypatch.setattr(app.webview, "create_window", lambda *a, **k: FakeWindow())
    monkeypatch.setattr(app.webview, "start", lambda *a, **k: started.update(k=k))
    app.main(["--debug"])
    assert started["k"]["debug"] is True


def test_frozen_index_path(monkeypatch, tmp_path):
    monkeypatch.setattr(app.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert app.ui_index_path() == tmp_path / "ui" / "index.html"


def test_emit_calls_window_wisp():
    emitter = app.Emitter()
    window = FakeWindow()
    emitter.attach(window)
    event = {"job": "a", "type": "done", "result": "x</script>"}
    emitter(event)
    assert window.scripts == ["window.__wisp(" + json.dumps(event) + ")"]


def test_emit_before_attach_and_after_close_is_silent():
    emitter = app.Emitter()
    emitter({"type": "library_changed"})
    window = FakeWindow()
    emitter.attach(window)
    emitter.detach()
    emitter({"type": "library_changed"})
    assert window.scripts == []


def test_emit_swallows_window_errors():
    emitter = app.Emitter()
    emitter.attach(FakeWindow(fail=True))
    emitter({"type": "library_changed"})


class StubApi:
    def __init__(self):
        self.added: list[str] = []

    def library_add_path(self, path: str) -> dict:
        self.added.append(path)
        if path.endswith("bad.ipa"):
            return {
                "ok": False,
                "error": {"code": "error.ipa_invalid", "params": {}, "detail": ""},
            }
        return {"ok": True, "data": {}}


def test_drop_adds_ipas_and_emits_library_changed():
    api, events = StubApi(), []
    drop = {
        "dataTransfer": {
            "files": [
                {"name": "a.IPA", "pywebviewFullPath": "C:/x/a.IPA"},
                {"name": "bad.ipa", "pywebviewFullPath": "C:/x/bad.ipa"},
                {"name": "notes.txt", "pywebviewFullPath": "C:/x/notes.txt"},
                {"name": "nopath.ipa"},
            ]
        }
    }
    app.handle_drop(api, events.append, drop)
    assert api.added == ["C:/x/a.IPA", "C:/x/bad.ipa"]
    assert events == [
        {
            "type": "library_changed",
            "added": 1,
            "ignored": 1,
            "unresolved": 1,
            "errors": [{"code": "error.ipa_invalid", "params": {}, "detail": ""}],
        }
    ]


def test_drop_with_malformed_event_is_ignored():
    events = []
    app.handle_drop(StubApi(), events.append, {"dataTransfer": None})
    app.handle_drop(StubApi(), events.append, {})
    assert events == []


def _age(path: Path, hours: float) -> None:
    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))


def test_sweep_removes_old_dirs_and_keeps_fresh_and_foreign(tmp_paths, tmp_path):
    work = tmp_path / "WS"
    for name in ("ab12", "fr35", "abc", "abcde", "ZZ99"):
        (work / name).mkdir(parents=True)
    (work / "ab12" / "f.txt").write_text("x")
    (work / "file").write_text("x")
    (work / "cd34").write_text("x")
    for name in ("ab12", "abc", "abcde", "ZZ99"):
        _age(work / name, 7)
    signed = tmp_paths.cache / "signed"
    (signed / "old").mkdir(parents=True)
    (signed / "new").mkdir()
    _age(signed / "old", 7)
    icons = tmp_paths.cache / "icons"
    icons.mkdir()

    app.sweep_stale(tmp_paths, work)

    assert not (work / "ab12").exists()
    assert not (signed / "old").exists()
    assert (work / "fr35").exists() and (work / "file").is_file()
    assert (work / "abc").exists() and (work / "abcde").exists()
    assert (work / "ZZ99").exists() and (work / "cd34").is_file()
    assert (signed / "new").exists() and icons.is_dir()


def test_sweep_does_not_follow_junction_named_like_work_dir(
    tmp_paths, tmp_path, monkeypatch
):
    monkeypatch.setattr(app, "STALE_AFTER_SECONDS", -1)
    work = tmp_path / "WS"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    _winapi.CreateJunction(str(outside), str(work / "ab12"))
    app.sweep_stale(tmp_paths, work)

    assert (outside / "keep.txt").exists()
    assert not (work / "ab12").exists()


def test_sweep_skips_linked_work_root(tmp_paths, tmp_path):
    real = tmp_path / "real"
    (real / "ab12").mkdir(parents=True)
    _age(real / "ab12", 7)
    root = tmp_path / "WS"
    _winapi.CreateJunction(str(real), str(root))

    app.sweep_stale(tmp_paths, root)

    assert (real / "ab12").exists()


def test_sweep_without_localappdata_touches_nothing(tmp_paths, tmp_path, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "WS" / "ab12").mkdir(parents=True)
    _age(tmp_path / "WS" / "ab12", 7)
    app.sweep_stale(tmp_paths)
    assert (tmp_path / "WS" / "ab12").exists()


def test_sweep_never_raises(tmp_paths, tmp_path, monkeypatch):
    work = tmp_path / "WS"
    (work / "ab12").mkdir(parents=True)
    _age(work / "ab12", 7)

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr(app.shutil, "rmtree", boom)
    app.sweep_stale(tmp_paths, work)
    app.sweep_stale(tmp_paths, tmp_path / "missing")
    assert (work / "ab12").exists()


class _DropEvent:
    def __init__(self):
        self._items: list = []

    def __iadd__(self, item):
        self._items.append(item)
        return self


def _window_with_drop(drop):
    events = type("Ev", (), {"drop": drop})()
    document = type("Doc", (), {"events": events})()
    return type("W", (), {"dom": type("D", (), {"document": document})()})()


def test_register_drop_registers_once():
    drop, handler = _DropEvent(), object()
    window = _window_with_drop(drop)
    app.register_drop(window, handler)
    app.register_drop(window, handler)
    assert drop._items == [handler]


def test_register_drop_logs_failure_without_raising(caplog):
    class Broken:
        @property
        def dom(self):
            raise RuntimeError("no dom")

    with caplog.at_level("WARNING"):
        app.register_drop(Broken(), object())
    assert "drop handler registration failed" in caplog.text
