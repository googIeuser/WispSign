import subprocess
import sys
from pathlib import Path

from wispsign.errors import WispError

_EXE_PARTS = ("zsign", "zsign.exe")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUCCESS_MARKER = "Signed OK"
_DETAIL_LIMIT = 2048
_REDACTED = "***"

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def zsign_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS).joinpath(*_EXE_PARTS)
    return _REPO_ROOT.joinpath("vendor", *_EXE_PARTS)


def _redacted_tail(output: str, password: str) -> str:
    if password:
        output = output.replace(password, _REDACTED)
    return output[-_DETAIL_LIMIT:]


class ZsignRunner:
    def __init__(self, exe: Path):
        self._exe = exe

    def sign(self, app_dir: Path, p12: Path, profile: Path, password: str) -> None:
        if not self._exe.is_file():
            raise WispError("error.zsign_missing")
        args = [str(self._exe), "-f", "-k", str(p12), "-p", password]
        args += ["-m", str(profile), str(app_dir)]
        try:
            result = subprocess.run(
                args,
                check=False,
                cwd=app_dir.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=_NO_WINDOW,
            )
        except OSError as exc:
            raise WispError(
                "error.sign_failed", f"cannot start zsign: {type(exc).__name__}"
            ) from None
        output = result.stdout.decode("utf-8", errors="replace")
        if result.returncode != 0 or _SUCCESS_MARKER not in output:
            raise WispError("error.sign_failed", _redacted_tail(output, password))
