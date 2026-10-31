pass

import copy
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPLACE_ATTEMPTS = 50
_REPLACE_DELAY_S = 0.01


def _replace_with_retry(src: str, dst: Path) -> None:
    pass
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_DELAY_S)


class JsonStore:
    def __init__(self, path: Path, default: Any):
        self._path = path
        self._default = default

    def load(self) -> Any:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return copy.deepcopy(self._default)
        except UnicodeDecodeError:
            return self._set_aside()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return self._set_aside()

    def save(self, data: Any) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2, ensure_ascii=False)

        fd, name = tempfile.mkstemp(
            dir=self._path.parent, prefix=self._path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            _replace_with_retry(name, self._path)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise

    def _set_aside(self) -> Any:
        pass
        self._quarantine()
        return copy.deepcopy(self._default)

    def _quarantine(self) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        os.replace(
            self._path, self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        )
