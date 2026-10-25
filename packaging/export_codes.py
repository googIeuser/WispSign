"""Write ui/src/lib/codes.json: every backend error.* and warn.* i18n code."""

import json
from pathlib import Path

from wispsign.certs.store import WARN_CODES
from wispsign.errors import ERROR_CODES

TARGET = Path(__file__).resolve().parent.parent / "ui" / "src" / "lib" / "codes.json"


def main() -> None:
    codes = sorted({*ERROR_CODES, *WARN_CODES})
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(codes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
