import json
from pathlib import Path

import pytest

from wispsign.errors import WispError
from wispsign.repos.parser import parse_source

URL = "https://example.com/repo.json"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "repos"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_altstore_v2():
    repo = parse_source(URL, load("altstore_v2.json"))
    app = repo.apps[0]
    assert app.version == "452.0.1" and app.download_url.startswith("https://")
    assert repo.name == "Example Source" and repo.url == URL
    assert app.size == 1234567 and app.developer == "Example Dev"
    assert app.repo_url == URL and repo.skipped == 0


def test_parse_legacy_format():
    repo = parse_source(URL, load("legacy.json"))
    assert repo.apps[0].bundle_id == "com.example.legacy"
    assert repo.apps[0].size == 4096
    assert repo.apps[0].icon_url is None  # http icon dropped


def test_parse_skips_invalid_apps_and_http_urls():
    repo = parse_source(URL, load("hostile.json"))
    assert repo.skipped == 3 and len(repo.apps) == 1
    assert repo.apps[0].description == "<script>alert(1)</script>"


def test_parse_rejects_missing_apps():
    with pytest.raises(WispError, match="repo_invalid"):
        parse_source(URL, {"name": "x"})


def test_parse_rejects_non_object():
    with pytest.raises(WispError, match="repo_invalid"):
        parse_source(URL, [1, 2])


def test_parse_non_list_apps():
    with pytest.raises(WispError, match="repo_invalid"):
        parse_source(URL, {"apps": "nope"})


def _one_app(icon: str, download: str) -> dict:
    return {
        "apps": [
            {
                "name": "A",
                "bundleIdentifier": "a.b",
                "iconURL": icon,
                "versions": [{"version": "1", "downloadURL": download}],
            }
        ]
    }


def test_parse_malformed_download_url_is_skipped_not_crash():
    repo = parse_source(URL, _one_app("https://x/i.png", "https://[x/a.ipa"))
    assert repo.skipped == 1 and repo.apps == ()


def test_malformed_icon_url_becomes_none():
    repo = parse_source(URL, _one_app("https://[bad/icon.png", "https://x/a.ipa"))
    assert repo.apps[0].icon_url is None


def _raw_app(name: str, bundle_id: str, version: str) -> dict:
    return {
        "name": name,
        "bundleIdentifier": bundle_id,
        "versions": [{"version": version, "downloadURL": "https://e.example/a.ipa"}],
    }


def test_parse_keeps_first_app_per_bundle_id_and_counts_duplicates():
    data = {
        "apps": [
            _raw_app("Demo App", "com.example.demo", "2.0"),
            _raw_app("Demo App Old", "com.example.demo", "1.0"),
            _raw_app("Sample", "com.example.sample", "1.0"),
            _raw_app("Demo App Again", "com.example.demo", "3.0"),
        ]
    }
    repo = parse_source(URL, data)
    assert [a.bundle_id for a in repo.apps] == [
        "com.example.demo",
        "com.example.sample",
    ]
    assert repo.apps[0].name == "Demo App"
    assert repo.skipped == 2
