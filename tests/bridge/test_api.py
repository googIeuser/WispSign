import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from appgen import PNG_1X1, make_ipa
from certgen import make_pair

from wispsign.bridge.api import PywebviewDialogs, WispApi, jsonable
from wispsign.certs.store import CertStore
from wispsign.device.service import DeviceInfo, DeviceService
from wispsign.errors import WispError
from wispsign.repos.models import Repo, RepoApp

REPO_URL = "https://r.example/repo.json"
APP = RepoApp(
    REPO_URL,
    "Remote",
    "com.remote.app",
    "2.0",
    "https://r.example/a.ipa",
    None,
    10,
    "",
    None,
)


class FakeDialogs:
    def __init__(self):
        self.answers: dict[str, list[str]] = {}
        self.asked: list[tuple[str, bool]] = []
        self.folder: str | None = None

    def open_files(self, kind, multiple):
        self.asked.append((kind, multiple))
        return self.answers.get(kind, [])

    def pick_folder(self):
        self.asked.append(("folder", False))
        return self.folder


class FakeBackend:
    def __init__(self):
        self.installed: list[tuple[Path, str]] = []
        self.uninstalled: list[tuple[str, str]] = []
        self.fail: Exception | None = None

    def list_devices(self):
        return [DeviceInfo("U1", "iPhone", "27.2", "iPhone17,1")]

    def install(self, ipa, udid, progress_cb):
        if self.fail:
            raise self.fail
        assert ipa.is_file()
        for p in (10, 100):
            progress_cb(p)
        self.installed.append((ipa, udid))

    def browse(self, udid):
        return {"com.a": {"CFBundleName": "A", "CFBundleShortVersionString": "1"}}

    def uninstall(self, bundle_id, udid):
        self.uninstalled.append((bundle_id, udid))


class FakeRepos:
    def __init__(self, tmp_path):
        self.urls: list[str] = []
        self.tmp_path = tmp_path
        self.downloads = 0
        self.progress = [(50, 100), (100, 100)]

    def add(self, url):
        if not url.startswith("https://"):
            raise WispError("error.url_not_https")
        self.urls.append(url)
        return Repo(url, "R", None, (APP,), 0)

    def remove(self, url):
        self.urls.remove(url)

    def list_urls(self):
        return list(self.urls)

    def cached(self, url):
        return Repo(url, "R", None, (APP,), 0)

    def refresh_all(self):
        return [Repo(REPO_URL, "R", None, (APP,), 0), WispError("error.network", "X")]

    def download(self, app, dest_dir, on_progress):
        for done, total in self.progress:
            on_progress(done, total)
        self.downloads += 1
        return make_ipa(self.tmp_path / f"dl{self.downloads}")


@pytest.fixture
def events():
    return []


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def dialogs():
    return FakeDialogs()


def _fake_sign(fail_at=None):
    def sign(req, certs, out_dir, on_step):
        for step in ("extract", "sign", "verify", "pack"):
            if step == fail_at:
                raise WispError("error.signature_invalid", "bad", bad=["x"])
            on_step(step)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "Test-signed.ipa"
        out.write_bytes(b"signed")
        sign.calls.append(req)
        return out

    sign.calls = []
    return sign


def _make(tmp_paths, tmp_path, events, backend, dialogs, sign=None, http=None):
    cond = threading.Condition()

    def emit(event):
        with cond:
            events.append(event)
            cond.notify_all()

    api = WispApi(
        tmp_paths,
        repos=FakeRepos(tmp_path),
        certs=CertStore(tmp_paths),
        devices=DeviceService(backend),
        dialogs=dialogs,
        emit=emit,
        sign=sign or _fake_sign(),
        http=http,
    )
    WAITERS[id(events)] = cond
    return api


WAITERS: dict[int, threading.Condition] = {}


@pytest.fixture
def api(tmp_paths, tmp_path, events, backend, dialogs):
    return _make(tmp_paths, tmp_path, events, backend, dialogs)


def wait_done(events, job):
    cond = WAITERS[id(events)]
    with cond:
        assert cond.wait_for(
            lambda: any(
                e["job"] == job and e["type"] in ("done", "error") for e in events
            ),
            timeout=10,
        )
    return [e for e in events if e["job"] == job]


def _json_roundtrip(value):
    return json.loads(json.dumps(value))


@pytest.fixture
def cert(tmp_paths):
    p12, profile, password = make_pair(app_id="*", devices=("U1",))
    return CertStore(tmp_paths).import_pair(p12, profile, password, "Fake")


@pytest.fixture
def entry_id(api, tmp_path):
    ipa = make_ipa(tmp_path / "lib")
    return api.library_add_path(str(ipa))["data"]["id"]


def test_api_never_raises(api):
    assert api.repos_add("http://x") == {
        "ok": False,
        "error": {"code": "error.url_not_https", "params": {}, "detail": ""},
    }


def test_unexpected_exception_wrapped(api):
    r = api.library_icon(object())
    assert r["ok"] is False and r["error"]["code"].startswith("error.")


def test_repos_flow(api):
    r = api.repos_add(REPO_URL)
    assert r["ok"] and r["data"]["apps"][0]["bundle_id"] == "com.remote.app"
    assert api.repos_list() == {"ok": True, "data": [REPO_URL]}
    api.repos_remove(REPO_URL)
    assert api.repos_list()["data"] == []


def test_repos_refresh_job(api, events):
    job = api.repos_refresh()["data"]
    final = wait_done(events, job)[-1]
    assert final["type"] == "done"
    repos = final["result"]
    assert repos[0]["name"] == "R"
    assert repos[1] == {"error": {"code": "error.network", "params": {}, "detail": "X"}}
    _json_roundtrip(final)


def test_repo_download_adds_to_library(api, events):
    api.repos_add(REPO_URL)
    job = api.repo_download(REPO_URL, "com.remote.app")["data"]
    evs = wait_done(events, job)
    assert evs[-1]["type"] == "done", evs
    assert evs[-1]["result"]["bundle_id"] == "com.remote.app"
    assert any(e.get("percent") == 50 for e in evs)
    assert len(api.library_list()["data"]) == 1


def test_same_app_downloaded_twice_gives_two_entries(api, events):
    api.repos_add(REPO_URL)
    for _ in range(2):
        job = api.repo_download(REPO_URL, "com.remote.app")["data"]
        assert wait_done(events, job)[-1]["type"] == "done"
    entries = api.library_list()["data"]
    assert len(entries) == 2 and entries[0]["path"] != entries[1]["path"]
    assert all(e["owned"] for e in entries)


def test_download_progress_only_when_the_percent_changes(api, events):
    api.repos_add(REPO_URL)
    total = 64 * 1000
    api._repos.progress = [(done, total) for done in range(0, total + 1, 64)]
    job = api.repo_download(REPO_URL, "com.remote.app")["data"]
    evs = wait_done(events, job)
    percents = [e["percent"] for e in evs if e["type"] == "progress"]
    assert percents == list(range(101))


def test_repo_download_unknown_app(api, events):
    api.repos_add(REPO_URL)
    job = api.repo_download(REPO_URL, "com.nope")["data"]
    assert wait_done(events, job)[-1]["error"]["code"] == "error.repo_invalid"


def test_library_add_files_via_dialog(api, dialogs, tmp_path):
    ipa = make_ipa(tmp_path / "a")
    dialogs.answers["ipa"] = [str(ipa)]
    r = api.library_add_files()
    assert dialogs.asked == [("ipa", True)]
    assert r["ok"] and len(r["data"]) == 1
    dialogs.answers["ipa"] = []
    assert api.library_add_files() == {"ok": True, "data": []}


def test_library_add_path_invalid(api, tmp_path):
    bad = tmp_path / "bad.ipa"
    bad.write_bytes(b"x")
    assert api.library_add_path(str(bad))["error"]["code"] == "error.ipa_invalid"


def test_library_icon_and_remove(api, entry_id):
    url = api.library_icon(entry_id)["data"]
    assert url.startswith("data:image/png;base64,")
    assert api.library_icon("zzz") == {"ok": True, "data": None}
    assert api.library_remove(entry_id)["ok"]
    assert api.library_list()["data"] == []


def _answer_cert_dialogs(dialogs, tmp_path, p12, profile):
    (tmp_path / "c.p12").write_bytes(p12)
    (tmp_path / "c.mobileprovision").write_bytes(profile)
    dialogs.answers["p12"] = [str(tmp_path / "c.p12")]
    dialogs.answers["mobileprovision"] = [str(tmp_path / "c.mobileprovision")]


def test_certs_import_flow(api, dialogs, tmp_path):
    p12, profile, password = make_pair()
    _answer_cert_dialogs(dialogs, tmp_path, p12, profile)
    r = api.certs_import("Mine", password)
    assert r["ok"], r
    _json_roundtrip(r)
    assert r["data"]["expires"].endswith("Z") and isinstance(r["data"]["devices"], list)
    listed = api.certs_list()["data"]
    assert [c["nickname"] for c in listed] == ["Mine"]
    warns = api.certs_validate(listed[0]["id"], "UNKNOWN-UDID")
    assert warns["ok"] and all({"code", "params"} <= set(w) for w in warns["data"])
    assert api.certs_remove(listed[0]["id"])["ok"]
    assert api.certs_list()["data"] == []


def test_certs_import_cancelled(api, dialogs):
    assert api.certs_import("x", "pw") == {"ok": True, "data": None}
    dialogs.answers["p12"] = ["C:/x.p12"]
    assert api.certs_import("x", "pw") == {"ok": True, "data": None}


def test_certs_import_wrong_password_no_leak(api, dialogs, tmp_path):
    p12, profile, _ = make_pair()
    _answer_cert_dialogs(dialogs, tmp_path, p12, profile)
    r = api.certs_import("x", "wrong-secret-pw")
    assert r["error"]["code"] == "error.p12_password"
    assert "wrong-secret-pw" not in json.dumps(r)


def test_device_endpoints(api, backend):
    assert api.device_list() == {
        "ok": True,
        "data": [
            {"udid": "U1", "name": "iPhone", "ios": "27.2", "model": "iPhone17,1"}
        ],
    }
    assert api.device_apps("U1")["data"][0]["bundle_id"] == "com.a"
    assert api.device_uninstall("U1", "com.a")["ok"]
    assert backend.uninstalled == [("com.a", "U1")]


def test_sign_and_install_emits_ordered_steps(api, events, backend, entry_id, cert):
    job = api.sign_and_install(entry_id, cert.id, "U1", "My", "com.my.app", None)[
        "data"
    ]
    evs = wait_done(events, job)
    assert evs[-1]["type"] == "done", evs
    steps = [
        e["step"] for e in evs if e["type"] == "progress" and e["step"] != "install"
    ]
    assert steps == ["extract", "sign", "verify", "pack"]
    installs = [e.get("percent") for e in evs if e.get("step") == "install"]
    assert installs[-1] == 100
    assert len(backend.installed) == 1 and backend.installed[0][1] == "U1"


@pytest.mark.parametrize(
    "pair,override,code",
    [
        ({"expires_days": 0}, None, "error.cert_expired"),
        ({"devices": ("OTHER",)}, None, "error.profile_device_missing"),
        ({"app_id": "com.other.app"}, None, "error.profile_app_id_mismatch"),
        ({}, "com.other.app", "error.profile_app_id_mismatch"),
    ],
)
def test_sign_rejects_ineligible_cert_before_signing(
    tmp_paths, tmp_path, events, backend, dialogs, pair, override, code
):
    p12, profile, password = make_pair(**{"devices": ("U1",), **pair})
    cert = CertStore(tmp_paths).import_pair(p12, profile, password, "Test")
    sign = _fake_sign()
    api = _make(tmp_paths, tmp_path, events, backend, dialogs, sign=sign)
    entry = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]

    job = api.sign_and_install(entry["id"], cert.id, "U1", None, override, None)["data"]

    last = wait_done(events, job)[-1]
    assert last["type"] == "error", last
    assert last["error"]["code"] == code
    assert sign.calls == [] and backend.installed == []
    assert not (tmp_paths.cache / "signed").exists()


def test_sign_rejects_unreadable_cert_before_signing(
    api, events, backend, entry_id, cert, tmp_paths
):
    (tmp_paths.certs / cert.id / "meta.json").write_bytes(b"broken")
    job = api.sign_and_install(entry_id, cert.id, "U1", None, None, None)["data"]
    last = wait_done(events, job)[-1]
    assert (
        last["type"] == "error" and last["error"]["code"] == "error.cert_meta_corrupt"
    )
    assert backend.installed == []


def test_sign_checks_the_overridden_bundle_id_and_allows_missing_push(
    tmp_paths, tmp_path, events, backend, dialogs
):
    p12, profile, password = make_pair(app_id="com.other.app", devices=("U1",))
    cert = CertStore(tmp_paths).import_pair(p12, profile, password, "Test")
    api = _make(tmp_paths, tmp_path, events, backend, dialogs)
    entry = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]
    job = api.sign_and_install(entry["id"], cert.id, "U1", None, "com.other.app", None)[
        "data"
    ]
    assert wait_done(events, job)[-1]["type"] == "done"
    assert len(backend.installed) == 1


def test_sign_and_install_passes_overrides_and_deletes_output(
    tmp_paths, tmp_path, events, backend, dialogs, cert
):
    sign = _fake_sign()
    api = _make(tmp_paths, tmp_path, events, backend, dialogs, sign=sign)
    eid = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]["id"]
    icon = tmp_path / "i.png"
    icon.write_bytes(PNG_1X1)
    job = api.sign_and_install(eid, cert.id, "U1", "My", "", str(icon))["data"]
    assert wait_done(events, job)[-1]["type"] == "done"
    req = sign.calls[0]
    assert (req.name, req.bundle_id, req.icon_png, req.cert_id) == (
        "My",
        None,
        PNG_1X1,
        cert.id,
    )
    assert not backend.installed[0][0].exists()
    entry = api.library_list()["data"][0]
    assert entry["id"] == eid and (tmp_paths.ipas / entry["path"]).exists()


@pytest.mark.parametrize("fail_at", ["extract", "sign", "verify", "pack"])
def test_sign_and_install_aborts_install_on_failure(
    tmp_paths, tmp_path, events, backend, dialogs, cert, fail_at
):
    api = _make(tmp_paths, tmp_path, events, backend, dialogs, sign=_fake_sign(fail_at))
    eid = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]["id"]
    job = api.sign_and_install(eid, cert.id, "U1", None, None, None)["data"]
    last = wait_done(events, job)[-1]
    assert (
        last["type"] == "error" and last["error"]["code"] == "error.signature_invalid"
    )
    assert backend.installed == []


def test_sign_and_install_install_failure_reported(
    api, events, backend, entry_id, cert
):
    backend.fail = RuntimeError("ApplicationVerificationFailed")
    job = api.sign_and_install(entry_id, cert.id, "U1", None, None, None)["data"]
    assert wait_done(events, job)[-1]["error"]["code"] == "error.signature_invalid"


def test_sign_and_install_unknown_entry(api, events, cert):
    job = api.sign_and_install("nope", cert.id, "U1", None, None, None)["data"]
    assert wait_done(events, job)[-1]["error"]["code"] == "error.entry_not_found"


def test_sign_and_install_bad_icon(api, events, entry_id, cert, tmp_path):
    job = api.sign_and_install(
        entry_id, cert.id, "U1", None, None, str(tmp_path / "no.png")
    )["data"]
    assert wait_done(events, job)[-1]["error"]["code"] == "error.io"


def test_settings(api, tmp_path):
    assert api.settings_get()["data"]["language"] is None
    assert api.settings_set({"language": "en"})["data"]["language"] == "en"
    assert api.settings_get()["data"]["language"] == "en"
    got = api.settings_set({"download_dir": str(tmp_path)})
    assert got["data"]["download_dir"] == str(tmp_path)


@pytest.mark.parametrize(
    "patch",
    [
        {"language": "de"},
        {"nope": 1},
        {"download_dir": 5},
        "str",
        {"language": "en", "x": 1},
    ],
)
def test_settings_rejects_bad_patch(api, patch):
    r = api.settings_set(patch)
    assert r["ok"] is False and r["error"]["code"] == "error.settings_invalid"
    assert api.settings_get()["data"]["language"] is None


def test_check_update(tmp_paths, tmp_path, events, backend, dialogs, monkeypatch):
    monkeypatch.setenv("WISPSIGN_UPDATE_REPO", "example/WispSign")
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"tag_name": "v99.0.0"})
        )
    )
    api = _make(tmp_paths, tmp_path, events, backend, dialogs, http=http)
    data = api.check_update()["data"]
    assert (data["status"], data["latest"]) == ("available", "v99.0.0")


def test_check_update_reports_failure(tmp_paths, tmp_path, events, backend, dialogs):
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    api = _make(tmp_paths, tmp_path, events, backend, dialogs, http=http)
    data = api.check_update()["data"]
    assert (data["status"], data["latest"]) == ("failed", None)


def test_get_state_is_json_safe(api, entry_id, cert):
    state = api.get_state()
    assert state["ok"]
    _json_roundtrip(state)
    assert state["data"]["settings"]["language"] is None
    assert len(state["data"]["library"]) == 1 and len(state["data"]["certs"]) == 1


@pytest.mark.parametrize(
    "repo,enabled", [(None, False), ("not a repo", False), ("example/WispSign", True)]
)
def test_get_state_reports_whether_update_checks_are_configured(
    api, monkeypatch, repo, enabled
):
    if repo is None:
        monkeypatch.delenv("WISPSIGN_UPDATE_REPO", raising=False)
    else:
        monkeypatch.setenv("WISPSIGN_UPDATE_REPO", repo)
    assert api.get_state()["data"]["updates"] is enabled


@pytest.mark.parametrize("bad", [None, ""])
def test_language_cannot_be_reset_to_unset(api, bad):
    assert api.settings_set({"language": bad})["ok"] is False


def test_broken_cert_never_fails_listing_and_can_be_removed(api, tmp_paths, cert):
    folder = tmp_paths.certs / "0123456789ab"
    folder.mkdir()
    (folder / "meta.json").write_text("{not json", encoding="utf-8")
    for listed in (api.certs_list()["data"], api.get_state()["data"]["certs"]):
        assert {(c["id"], c["broken"]) for c in listed} == {
            (cert.id, False),
            ("0123456789ab", True),
        }
    assert api.certs_remove("0123456789ab")["ok"]
    assert not folder.exists()
    assert [c["id"] for c in api.certs_list()["data"]] == [cert.id]


def test_certs_validate_checks_the_bundle_id(api, tmp_paths):
    p12, profile, password = make_pair(app_id="com.example.demo", push=True)
    rec = CertStore(tmp_paths).import_pair(p12, profile, password, "x")
    codes = [w["code"] for w in api.certs_validate(rec.id, None)["data"]]
    assert codes == []
    got = api.certs_validate(rec.id, None, "com.example.other")["data"]
    assert got == [
        {
            "code": "warn.app_id_mismatch",
            "params": {"app_id": "com.example.demo", "bundle_id": "com.example.other"},
        }
    ]


def test_pick_icon(api, dialogs):
    assert api.pick_icon() == {"ok": True, "data": None}
    dialogs.answers["png"] = ["C:/a.png"]
    assert api.pick_icon() == {"ok": True, "data": "C:/a.png"}
    assert dialogs.asked[-1] == ("png", False)


def test_pick_folder(api, dialogs):
    assert api.pick_folder() == {"ok": True, "data": None}
    dialogs.folder = "C:/Downloads"
    assert api.pick_folder() == {"ok": True, "data": "C:/Downloads"}
    assert dialogs.asked[-1] == ("folder", False)


class _FolderWindow:
    def __init__(self, picked):
        self.picked = picked
        self.kinds: list[int] = []

    def create_file_dialog(self, kind, **kwargs):
        self.kinds.append(kind)
        return self.picked


def test_pywebview_folder_dialog():
    import webview

    dialogs = PywebviewDialogs()
    assert dialogs.pick_folder() is None
    window = _FolderWindow(("C:/Downloads",))
    dialogs.bind_window(window)
    assert dialogs.pick_folder() == "C:/Downloads"
    assert window.kinds == [webview.FOLDER_DIALOG]
    window.picked = None
    assert dialogs.pick_folder() is None


def test_no_public_attributes_exposed_to_js(api):
    assert [n for n in vars(api) if not n.startswith("_")] == []


def test_jsonable_converts_types():
    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert jsonable({"a": (stamp, Path("x"))}) == {"a": ["2026-01-02T03:04:05Z", "x"]}





def test_job_result_available_for_fast_job(api, events):
    job = api.repos_refresh()["data"]
    wait_done(events, job)
    res = api.job_result(job)
    assert res["ok"] and res["data"]["type"] == "done" and res["data"]["job"] == job
    assert api.job_result("unknown") == {"ok": True, "data": None}


def test_repo_download_registers_in_download_dir(api, events, tmp_path):
    dest = tmp_path / "dls"
    dest.mkdir()
    assert api.settings_set({"download_dir": str(dest)})["ok"]
    api.repos_add(REPO_URL)
    seen = {}
    real = api._repos.download

    def spy(app, dest_dir, cb):
        seen["dest"] = dest_dir
        return real(app, dest_dir, cb)

    api._repos.download = spy
    job = api.repo_download(REPO_URL, "com.remote.app")["data"]
    assert wait_done(events, job)[-1]["type"] == "done"
    assert seen["dest"] == dest
    assert len(api.library_list()["data"]) == 1


def test_repo_download_unlisted_repo_rejected(api, events):
    job = api.repo_download("https://evil.example/r.json", "com.remote.app")["data"]
    assert wait_done(events, job)[-1]["error"]["code"] == "error.repo_invalid"


def test_repo_download_does_not_refresh_all(api, events):
    api.repos_add(REPO_URL)
    api._repos.refresh_all = lambda: pytest.fail("refresh_all must not be used")
    job = api.repo_download(REPO_URL, "com.remote.app")["data"]
    assert wait_done(events, job)[-1]["type"] == "done"


@pytest.mark.parametrize("bad", ["relative/dir", "", "C:/definitely/missing/dir"])
def test_download_dir_must_be_absolute_existing_dir(api, bad):
    r = api.settings_set({"download_dir": bad})
    assert r["error"]["code"] == "error.settings_invalid"


def test_download_dir_rejects_file(api, tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    assert api.settings_set({"download_dir": str(f)})["ok"] is False


def test_sign_output_dir_is_per_job_and_cleaned_on_success(
    tmp_paths, tmp_path, events, backend, dialogs, cert
):
    dirs = []
    base = _fake_sign()

    def sign(req, certs, out_dir, on_step):
        dirs.append(out_dir)
        return base(req, certs, out_dir, on_step)

    api = _make(tmp_paths, tmp_path, events, backend, dialogs, sign=sign)
    eid = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]["id"]
    jobs = [
        api.sign_and_install(eid, cert.id, "U1", None, None, None)["data"]
        for _ in range(2)
    ]
    for j in jobs:
        assert wait_done(events, j)[-1]["type"] == "done"
    assert len(set(dirs)) == 2 and all(not d.exists() for d in dirs)
    assert list((tmp_paths.cache / "signed").iterdir()) == []


def test_sign_output_dir_cleaned_on_install_failure(
    tmp_paths, tmp_path, events, backend, dialogs, cert
):
    backend.fail = RuntimeError("boom")
    api = _make(tmp_paths, tmp_path, events, backend, dialogs)
    eid = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]["id"]
    job = api.sign_and_install(eid, cert.id, "U1", None, None, None)["data"]
    assert wait_done(events, job)[-1]["type"] == "error"
    assert list((tmp_paths.cache / "signed").iterdir()) == []


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"GIF89a....", id="not-png"),
        pytest.param(b"", id="empty"),
        pytest.param(PNG_1X1 + b"0" * (9 * 1024 * 1024), id="too-big"),
    ],
)
def test_icon_must_be_small_png(api, events, entry_id, cert, tmp_path, content):
    icon = tmp_path / "i.png"
    icon.write_bytes(content)
    job = api.sign_and_install(entry_id, cert.id, "U1", None, None, str(icon))["data"]
    assert wait_done(events, job)[-1]["error"]["code"] == "error.icon_invalid"


def test_concurrent_settings_sets_keep_valid_json(api, tmp_paths, tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    threads = [
        threading.Thread(
            target=lambda i=i: api.settings_set({"language": "en" if i % 2 else "tr"})
        )
        for i in range(30)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert json.loads(tmp_paths.settings.read_text())["language"] in ("tr", "en")


def _write(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_cache_clear_empties_cache_and_reports_freed_bytes(api, tmp_paths, entry_id):
    _write(tmp_paths.cache / "repos" / "abc.json", 10)
    _write(tmp_paths.cache / "signed" / "old1" / "Left-signed.ipa", 5)
    _write(tmp_paths.cache / "icons" / "orphan123456.png", 3)
    _write(tmp_paths.cache / "stray.bin", 2)
    protected = [tmp_paths.library, tmp_paths.settings]
    api.settings_set({"language": "en"})
    before = {p: p.read_bytes() for p in protected}
    ipas_before = sorted(p.name for p in tmp_paths.ipas.iterdir())

    r = api.cache_clear()

    assert r["ok"] is True
    assert r["data"] >= 20
    assert not (tmp_paths.cache / "repos" / "abc.json").exists()
    assert not (tmp_paths.cache / "signed" / "old1").exists()
    assert not (tmp_paths.cache / "icons" / "orphan123456.png").exists()
    assert not (tmp_paths.cache / "stray.bin").exists()
    assert tmp_paths.cache.is_dir()
    assert {p: p.read_bytes() for p in protected} == before
    assert sorted(p.name for p in tmp_paths.ipas.iterdir()) == ipas_before
    assert api.library_list()["data"][0]["id"] == entry_id


def test_cache_clear_keeps_icons_of_library_entries(api, tmp_paths, entry_id):
    icon = _write(tmp_paths.cache / "icons" / f"{entry_id}.png", 4)
    assert api.cache_clear()["ok"] is True
    assert icon.is_file()


def test_cache_clear_never_touches_certs(api, tmp_paths, cert):
    before = sorted(p.relative_to(tmp_paths.certs) for p in tmp_paths.certs.rglob("*"))
    assert api.cache_clear()["ok"] is True
    assert (
        sorted(p.relative_to(tmp_paths.certs) for p in tmp_paths.certs.rglob("*"))
        == before
    )
    assert api.certs_list()["data"][0]["id"] == cert.id


def test_cache_clear_on_empty_cache_frees_nothing(api, tmp_paths):
    assert api.cache_clear() == {"ok": True, "data": 0}


def test_cache_clear_skips_output_of_running_sign_job(
    tmp_paths, tmp_path, events, backend, dialogs, cert
):
    started = threading.Event()
    release = threading.Event()
    seen: list[Path] = []
    base = _fake_sign()

    def sign(req, certs, out_dir, on_step):
        _write(out_dir / "partial.bin", 7)
        seen.append(out_dir)
        started.set()
        assert release.wait(timeout=10)
        return base(req, certs, out_dir, on_step)

    api = _make(tmp_paths, tmp_path, events, backend, dialogs, sign=sign)
    eid = api.library_add_path(str(make_ipa(tmp_path / "lib")))["data"]["id"]
    _write(tmp_paths.cache / "signed" / "stale" / "x.ipa", 3)
    job = api.sign_and_install(eid, cert.id, "U1", None, None, None)["data"]
    assert started.wait(timeout=10)

    r = api.cache_clear()
    kept = (seen[0] / "partial.bin").is_file()

    release.set()
    assert r["ok"] is True
    assert kept
    assert not (tmp_paths.cache / "signed" / "stale").exists()
    assert wait_done(events, job)[-1]["type"] == "done"


def _outside_dir(tmp_path: Path) -> tuple[Path, Path]:
    outside = tmp_path / "outside"
    keep = _write(outside / "precious.txt", 9)
    return outside, keep


def test_cache_clear_removes_junction_without_following_it(api, tmp_paths, tmp_path):
    _winapi = pytest.importorskip("_winapi")
    outside, precious = _outside_dir(tmp_path)
    tmp_paths.cache.mkdir(parents=True, exist_ok=True)
    link = tmp_paths.cache / "junction"
    _winapi.CreateJunction(str(outside), str(link))
    assert link.is_dir()

    r = api.cache_clear()

    assert r["ok"] is True
    assert precious.read_bytes() == b"x" * 9
    assert not os.path.lexists(link)


def test_cache_clear_removes_dir_symlink_without_following_it(api, tmp_paths, tmp_path):
    outside, precious = _outside_dir(tmp_path)
    tmp_paths.cache.mkdir(parents=True, exist_ok=True)
    link = tmp_paths.cache / "dirlink"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks needs Developer Mode or admin")

    r = api.cache_clear()

    assert r["ok"] is True
    assert precious.read_bytes() == b"x" * 9
    assert not os.path.lexists(link)


def test_cache_clear_refuses_a_cache_folder_that_is_a_junction(tmp_path, tmp_paths):
    _winapi = pytest.importorskip("_winapi")
    outside, precious = _outside_dir(tmp_path)
    paths = type(tmp_paths)(tmp_path / "linked-root")
    paths.root.mkdir()
    _winapi.CreateJunction(str(outside), str(paths.cache))
    api = WispApi(paths, repos=FakeRepos(tmp_path), dialogs=FakeDialogs())

    r = api.cache_clear()

    assert r["ok"] is False and r["error"]["code"] == "error.io"
    assert precious.is_file()
