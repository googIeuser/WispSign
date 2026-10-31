pass

import os
import re
from dataclasses import dataclass
from typing import Literal

import httpx

TIMEOUT_SECONDS = 10.0
_VERSION = re.compile(r"v?(\d+(?:\.\d+)*)")
_REPO = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class UpdateCheck:

    status: Literal["available", "current", "failed"]
    latest: str | None


_FAILED = UpdateCheck("failed", None)


def _parse(text: object) -> tuple[int, ...] | None:
    if not isinstance(text, str):
        return None
    match = _VERSION.fullmatch(text.strip())
    return tuple(int(p) for p in match.group(1).split(".")) if match else None


def _pad(version: tuple[int, ...], size: int) -> tuple[int, ...]:
    return version + (0,) * (size - len(version))


def update_repo() -> str | None:
    pass

    repo = os.environ.get("WISPSIGN_UPDATE_REPO", "")
    return repo if _REPO.fullmatch(repo) else None


def check_latest(
    current: str, repo: str | None = None, http: httpx.Client | None = None
) -> UpdateCheck:
    pass
    repo = (update_repo() or "") if repo is None else repo
    if not _REPO.fullmatch(repo):
        return _FAILED
    client = http or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        response = client.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        tag = response.json().get("tag_name")
    except (httpx.HTTPError, ValueError, AttributeError):
        return _FAILED
    latest, running = _parse(tag), _parse(current)
    if latest is None or running is None:
        return _FAILED
    size = max(len(latest), len(running))
    if _pad(latest, size) > _pad(running, size):
        return UpdateCheck("available", tag)
    return UpdateCheck("current", None)
