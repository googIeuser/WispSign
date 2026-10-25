import httpx
import pytest

from wispsign.updates import UpdateCheck, check_latest


@pytest.fixture(autouse=True)
def release_endpoint(monkeypatch):
    monkeypatch.setenv("WISPSIGN_UPDATE_REPO", "example/WispSign")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _release(tag, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(str(request.url))
        return httpx.Response(200, json={"tag_name": tag})

    return handler


FAILED = UpdateCheck("failed", None)


def test_newer_release_returned_and_url_pinned():
    seen = []
    got = check_latest("0.1.0", http=_client(_release("v0.2.0", seen)))
    assert got == UpdateCheck("available", "v0.2.0")
    assert seen == ["https://api.github.com/repos/example/WispSign/releases/latest"]


def test_unconfigured_update_check_does_not_contact_a_personal_account(monkeypatch):
    monkeypatch.delenv("WISPSIGN_UPDATE_REPO", raising=False)

    def handler(request):
        pytest.fail("no release endpoint is configured")

    assert check_latest("0.1.0", http=_client(handler)) == FAILED


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("owner/repo?token=demo", None),
        ("example/WispSign", "example/WispSign"),
    ],
)
def test_update_repo_is_only_a_valid_configured_target(monkeypatch, value, expected):
    from wispsign.updates import update_repo

    if value is None:
        monkeypatch.delenv("WISPSIGN_UPDATE_REPO", raising=False)
    else:
        monkeypatch.setenv("WISPSIGN_UPDATE_REPO", value)
    assert update_repo() == expected


@pytest.mark.parametrize(
    "repo", ["", "https://example.com/repo", "owner/repo?token=demo"]
)
def test_invalid_release_target_does_not_make_a_request(repo):
    def handler(request):
        pytest.fail("an invalid release target must not be requested")

    assert check_latest("0.1.0", repo=repo, http=_client(handler)) == FAILED


def test_same_or_older_is_up_to_date():
    current = UpdateCheck("current", None)
    assert check_latest("0.2.0", http=_client(_release("v0.2.0"))) == current
    assert check_latest("1.0.0", http=_client(_release("v0.9.9"))) == current


def test_numeric_not_lexicographic_compare():
    got = check_latest("0.9.0", http=_client(_release("0.10.0")))
    assert got == UpdateCheck("available", "0.10.0")


def test_offline_is_a_failure_not_up_to_date():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    assert check_latest("0.1.0", http=_client(handler)) == FAILED


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(404),
        lambda r: httpx.Response(200, text="x"),
        lambda r: httpx.Response(200, json=[1]),
        _release("nightly"),
        _release(5),
    ],
)
def test_bad_status_or_body_is_a_failure(handler):
    assert check_latest("0.1.0", http=_client(handler)) == FAILED


def test_unparsable_running_version_is_a_failure():
    assert check_latest("dev", http=_client(_release("v0.2.0"))) == FAILED
