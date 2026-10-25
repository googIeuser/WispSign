"""Filesystem locations used by WispSign."""

import os
import secrets
import string
from dataclasses import dataclass
from pathlib import Path

_ALPHABET = string.ascii_lowercase + string.digits
_WORK_NAME_LEN = 4


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def settings(self) -> Path:
        return self.root / "settings.json"

    @property
    def repos(self) -> Path:
        return self.root / "repos.json"

    @property
    def library(self) -> Path:
        return self.root / "library.json"

    @property
    def certs(self) -> Path:
        return self.root / "certs"

    @property
    def ipas(self) -> Path:
        return self.root / "ipas"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    def ensure(self) -> None:
        for directory in (self.root, self.certs, self.ipas, self.cache):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default(cls) -> "AppPaths":
        return cls(Path(os.environ["APPDATA"]) / "WispSign")


def _random_name() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_WORK_NAME_LEN))


def make_work_dir(base: Path | None = None) -> Path:
    r"""Create a uniquely named short directory under base (default %LOCALAPPDATA%\WS)."""
    parent = base if base is not None else Path(os.environ["LOCALAPPDATA"]) / "WS"
    parent.mkdir(parents=True, exist_ok=True)
    while True:
        candidate = parent / _random_name()
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
