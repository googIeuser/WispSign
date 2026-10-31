pass

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def jsonable(value: Any) -> Any:
    pass
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    return value
