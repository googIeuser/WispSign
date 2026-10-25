import json
import os
import time
from pathlib import Path

import httpx
import pytest

from wispsign.errors import WispError
from wispsign.repos import client as client_module
from wispsign.repos.client import RepoClient

URL = "https://example.com/repo.json"
IPA_URL = "https://example.com/app.ipa"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "repos"
REPO_BYTES = (FIXTURES / "altstore_v2.json").read_bytes()
IPA_BYTES = b"x" * 300_000


class Server:
    def __init__(self):
        self.online = True
        self.repo_body = REPO_BYTES
        self.seen: list[str] = []
        self.redirects: dict[str, str] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(str(request.url))
        if not self.online:
            raise httpx.ConnectError("offline", request=request)
        target = self.redirects.get(str(request.url))
        if target:
            return httpx.Response(302, headers={"location": target})
        if request.url.path.endswith(".ipa"):
            return httpx.Response(
                200, content=IPA_BYTES, headers={"content-length": str(len(IPA_BYTES))}
            )
        return httpx.Response(200, content=self.repo_body)


@pytest.fixture
def server():
    return Server()


@pytest.fixture
def client(tmp_paths, server):
    http = httpx.Client(transport=httpx.MockTransport(server))
    return RepoClient(tmp_paths, http)


def test_add_rejects_non_https(client):
    with pytest.raises(WispError, match="url_not_https"):
        client.add("http://x/repo.json")


def test_add_returns_repo_and_persists(client, tmp_paths):
    repo = client.add(URL)
    assert repo.name == "Example Source"
    entries = json.loads(tmp_paths.repos.read_text(encoding="utf-8"))
    assert entries[0]["url"] == URL and entries[0]["name"] == "Example Source"
    assert entries[0]["addedAt"].endswith("Z") or "+00:00" in entries[0]["addedAt"]


def test_fetch_rejects_oversize(client, server):
    server.repo_body = b"{" + b" " * (6 * 1024 * 1024) + b"}"
    with pytest.raises(WispError, match="repo_too_large"):
        client.add(URL)


def test_add_invalid_json(client, server):
    server.repo_body = b"not json"
    with pytest.raises(WispError, match="repo_invalid"):
        client.add(URL)


def test_add_duplicate_is_noop(client):
    client.add(URL)
    client.add(URL)
    assert client.list_urls() == [URL]


def test_remove(client):
    client.add(URL)
    client.remove(URL)
    assert client.list_urls() == []


def test_failed_add_does_not_persist(client, server):
    server.online = False
    with pytest.raises(WispError, match="network"):
        client.add(URL)
    assert client.list_urls() == []


def test_refresh_uses_cache_when_offline(client, server):
    client.add(URL)
    (first,) = client.refresh_all()
    server.online = False
    (second,) = client.refresh_all()
    assert not isinstance(second, WispError)
    assert second == first


def test_refresh_offline_without_cache_returns_error(tmp_paths, server):
    c = RepoClient(tmp_paths, httpx.Client(transport=httpx.MockTransport(server)))
    c.add(URL)
    for f in (tmp_paths.cache / "repos").glob("*.json"):
        f.unlink()
    server.online = False
    (result,) = c.refresh_all()
    assert isinstance(result, WispError) and result.code == "error.network"


def test_download_reports_progress_and_writes_file(client, tmp_path):
    app = client.add(URL).apps[0]
    app = type(app)(**{**app.__dict__, "download_url": IPA_URL})
    progress: list[tuple[int, int | None]] = []
    dest = tmp_path / "dl"
    path = client.download(
        app, dest, lambda done, total: progress.append((done, total))
    )
    total = len(IPA_BYTES)
    assert progress[-1] == (total, total)
    assert path.read_bytes() == IPA_BYTES
    assert not list(dest.glob("*.part"))


def test_download_failure_removes_part(client, server, tmp_path):
    app = client.add(URL).apps[0]
    server.online = False
    dest = tmp_path / "dl"
    with pytest.raises(WispError, match="network"):
        client.download(app, dest, lambda done, total: None)
    assert not list(dest.glob("*.part"))


@pytest.mark.parametrize("advertised_size", [None, "10", "100"])
def test_download_aborts_oversized_ipa_and_removes_partial_files(
    client, tmp_paths, tmp_path, monkeypatch, advertised_size
):
    app = _ipa_app(client)
    monkeypatch.setattr(client_module, "MAX_IPA_BYTES", 16, raising=False)
    headers = {} if advertised_size is None else {"content-length": advertised_size}
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=iter([b"x" * 10, b"x" * 10]), headers=headers
            )
        )
    )
    limited = RepoClient(tmp_paths, http)
    dest = tmp_path / "limited"
    with pytest.raises(WispError, match="ipa_too_large"):
        limited.download(app, dest, lambda done, total: None)
    assert not list(dest.iterdir())


def _ipa_app(client):
    app = client.add(URL).apps[0]
    return type(app)(**{**app.__dict__, "download_url": IPA_URL})


def test_fetch_rejects_https_to_http_redirect(client, server):
    server.redirects[URL] = "http://evil.example/repo.json"
    with pytest.raises(WispError, match="url_not_https"):
        client.add(URL)
    assert not any(u.startswith("http://") for u in server.seen)


def test_fetch_rejects_https_http_https_chain(client, server):
    server.redirects[URL] = "http://evil.example/hop"
    server.redirects["http://evil.example/hop"] = "https://example.com/final.json"
    with pytest.raises(WispError, match="url_not_https"):
        client.add(URL)
    assert not any(u.startswith("http://") for u in server.seen)


def test_fetch_follows_https_redirect(client, server):
    server.redirects[URL] = "https://example.com/other.json"
    assert client.add(URL).name == "Example Source"


def test_fetch_redirect_loop_is_network_error(client, server):
    server.redirects[URL] = URL
    with pytest.raises(WispError, match="network"):
        client.add(URL)


def test_download_rejects_https_to_http_redirect(client, server, tmp_path):
    app = _ipa_app(client)
    server.redirects[IPA_URL] = "http://evil.example/app.ipa"
    server.seen.clear()
    dest = tmp_path / "dl"
    with pytest.raises(WispError, match="url_not_https"):
        client.download(app, dest, lambda done, total: None)
    assert not any(u.startswith("http://") for u in server.seen)
    assert not list(dest.glob("*"))


def test_add_malformed_url_is_wisp_error(client):
    with pytest.raises(WispError, match="url_not_https"):
        client.add("https://[x/repo.json")


def test_add_invalid_port_url_is_wisp_error(client):
    with pytest.raises(WispError, match="url_not_https"):
        client.add("https://example.com:abc/repo.json")


def test_add_deeply_nested_json_is_repo_invalid(client, server):
    server.repo_body = b"[" * 200_000 + b"]" * 200_000
    with pytest.raises(WispError, match="repo_invalid"):
        client.add(URL)


def test_download_progress_callback_failure_removes_part(client, tmp_path):
    app = _ipa_app(client)
    dest = tmp_path / "dl"

    def boom(done, total):
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError):
        client.download(app, dest, boom)
    assert not list(dest.glob("*"))


def test_download_stream_error_removes_part(client, tmp_paths, tmp_path):
    app = _ipa_app(client)

    def flaky(request):
        def body():
            yield b"x" * 1000
            raise httpx.ReadError("cut", request=request)

        return httpx.Response(200, content=body())

    c = RepoClient(tmp_paths, httpx.Client(transport=httpx.MockTransport(flaky)))
    dest = tmp_path / "dl"
    seen: list[int] = []
    with pytest.raises(WispError, match="network"):
        c.download(app, dest, lambda done, total: seen.append(done))
    assert not list(dest.glob("*"))


def test_download_long_names_are_capped(client, tmp_path):
    app = _ipa_app(client)
    app = type(app)(**{**app.__dict__, "bundle_id": "a" * 500})
    path = client.download(app, tmp_path / "dl", lambda done, total: None)
    assert len(path.name) < 100 and path.exists()


@pytest.mark.parametrize("location", ["https://[x/b", "//[x/b"])
def test_fetch_malformed_location_is_wisp_error(client, server, location):
    server.redirects[URL] = location
    with pytest.raises(WispError, match="url_not_https"):
        client.add(URL)


@pytest.mark.parametrize("location", ["https://[x/b", "//[x/b"])
def test_download_malformed_location_is_wisp_error(client, server, tmp_path, location):
    app = _ipa_app(client)
    server.redirects[IPA_URL] = location
    dest = tmp_path / "dl"
    with pytest.raises(WispError, match="url_not_https"):
        client.download(app, dest, lambda done, total: None)
    assert not list(dest.glob("*"))


def test_cached_uses_cache_without_network(tmp_paths, server):
    client = RepoClient(
        tmp_paths, http=httpx.Client(transport=httpx.MockTransport(server))
    )
    client.add(URL)
    server.seen.clear()
    server.online = False
    assert client.cached(URL).apps
    assert server.seen == []


def test_cached_fetches_only_that_url_on_miss(tmp_paths, server):
    client = RepoClient(
        tmp_paths, http=httpx.Client(transport=httpx.MockTransport(server))
    )
    assert client.cached(URL).apps
    assert server.seen == [URL]


def test_download_twice_gives_two_files(client, tmp_path):
    app = _ipa_app(client)
    dest = tmp_path / "dl"
    first = client.download(app, dest, lambda done, total: None)
    second = client.download(app, dest, lambda done, total: None)
    assert first != second
    assert first.read_bytes() == second.read_bytes() == IPA_BYTES
    assert sorted(p.name for p in dest.iterdir()) == sorted([first.name, second.name])


def test_download_never_overwrites_user_files(client, tmp_path):
    app = _ipa_app(client)
    dest = tmp_path / "dl"
    user_ipa = client.download(app, dest, lambda done, total: None)
    user_ipa.write_bytes(b"user ipa")  # now stands for a file the user put there
    user_part = dest / (user_ipa.name.removesuffix(".ipa") + "-2.ipa.part")
    user_part.write_bytes(b"user part")
    path = client.download(app, dest, lambda done, total: None)
    assert path not in (user_ipa, user_part)
    assert user_ipa.read_bytes() == b"user ipa"
    assert user_part.read_bytes() == b"user part"
    assert path.read_bytes() == IPA_BYTES


def test_download_failure_keeps_user_file(client, server, tmp_path):
    app = _ipa_app(client)
    dest = tmp_path / "dl"
    user_ipa = client.download(app, dest, lambda done, total: None)
    user_ipa.write_bytes(b"user ipa")
    server.online = False
    with pytest.raises(WispError, match="network"):
        client.download(app, dest, lambda done, total: None)
    assert [p.name for p in dest.iterdir()] == [user_ipa.name]
    assert user_ipa.read_bytes() == b"user ipa"


SEVEN_HOURS = 7 * 60 * 60


def _leftover(client, dest, ipa_bytes=b"", part_bytes=b"partial", age=SEVEN_HOURS):
    """The pair a hard-killed download leaves: placeholder ``.ipa`` + ``.ipa.part``."""
    name = client.download(_ipa_app(client), dest, lambda d, t: None)
    name.unlink()
    part = name.with_name(name.name + ".part")
    name.write_bytes(ipa_bytes)
    part.write_bytes(part_bytes)
    old = time.time() - age
    for path in (name, part):
        os.utime(path, (old, old))
    return name, part


def test_download_clears_a_stale_crashed_reservation(client, tmp_path):
    dest = tmp_path / "dl"
    name, part = _leftover(client, dest)
    path = client.download(_ipa_app(client), dest, lambda d, t: None)
    assert path == name and path.read_bytes() == IPA_BYTES
    assert not part.exists()
    assert sorted(p.name for p in dest.iterdir()) == [name.name]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"age": 60},  # a download that may still be running
        {"ipa_bytes": b"a real file"},  # never delete a non-empty .ipa
    ],
)
def test_download_keeps_reservations_that_may_not_be_leftovers(
    client, tmp_path, kwargs
):
    dest = tmp_path / "dl"
    name, part = _leftover(client, dest, **kwargs)
    before = (name.read_bytes(), part.read_bytes())
    path = client.download(_ipa_app(client), dest, lambda d, t: None)
    assert path not in (name, part)
    assert (name.read_bytes(), part.read_bytes()) == before


def test_download_keeps_a_stale_part_without_its_placeholder(client, tmp_path):
    dest = tmp_path / "dl"
    name, part = _leftover(client, dest)
    name.unlink()
    client.download(_ipa_app(client), dest, lambda d, t: None)
    assert part.read_bytes() == b"partial"


def test_overlapping_downloads_use_separate_files(client, tmp_path):
    app = _ipa_app(client)
    dest = tmp_path / "dl"
    inner: list[Path] = []

    def start_second_download(done, total):
        if not inner:  # a second download of the same app while the first runs
            inner.append(client.download(app, dest, lambda d, t: None))

    outer = client.download(app, dest, start_second_download)
    assert outer != inner[0]
    assert outer.read_bytes() == inner[0].read_bytes() == IPA_BYTES
    assert not list(dest.glob("*.part"))
