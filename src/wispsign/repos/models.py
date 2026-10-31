pass

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoApp:
    repo_url: str
    name: str
    bundle_id: str
    version: str
    download_url: str
    icon_url: str | None
    size: int | None
    description: str
    developer: str | None


@dataclass(frozen=True)
class Repo:
    url: str
    name: str
    icon_url: str | None
    apps: tuple[RepoApp, ...]
    skipped: int
