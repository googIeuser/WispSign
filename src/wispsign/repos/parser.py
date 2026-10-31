pass

from typing import TypeGuard
from urllib.parse import urlparse

from wispsign.errors import WispError
from wispsign.repos.models import Repo, RepoApp


def is_https(url: object) -> TypeGuard[str]:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _https_or_none(value: object) -> str | None:
    return value if is_https(value) else None


def _size(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _release(raw: dict) -> dict:
    pass
    versions = raw.get("versions")
    if isinstance(versions, list) and versions and isinstance(versions[0], dict):
        return versions[0]
    return raw


def _parse_app(repo_url: str, raw: object) -> RepoApp | None:
    if not isinstance(raw, dict):
        return None
    release = _release(raw)
    name = _text(raw.get("name"))
    bundle_id = _text(raw.get("bundleIdentifier"))
    version = _text(release.get("version"))
    download_url = _https_or_none(release.get("downloadURL"))
    if not (name and bundle_id and version and download_url):
        return None
    description = raw.get("localizedDescription")
    return RepoApp(
        repo_url=repo_url,
        name=name,
        bundle_id=bundle_id,
        version=version,
        download_url=download_url,
        icon_url=_https_or_none(raw.get("iconURL")),
        size=_size(release.get("size")),
        description=description if isinstance(description, str) else "",
        developer=_text(raw.get("developerName")),
    )


def parse_source(url: str, data: object) -> Repo:
    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
        raise WispError("error.repo_invalid")
    apps = [_parse_app(url, raw) for raw in data["apps"]]

    unique: dict[str, RepoApp] = {}
    for app in apps:
        if app is not None and app.bundle_id not in unique:
            unique[app.bundle_id] = app
    return Repo(
        url=url,
        name=_text(data.get("name")) or url,
        icon_url=_https_or_none(data.get("iconURL")),
        apps=tuple(unique.values()),
        skipped=len(apps) - len(unique),
    )
