import hashlib
import os
import plistlib
import re
from dataclasses import dataclass
from pathlib import Path
from xml.parsers.expat import ExpatError

from wispsign.signing.ipa import long_path

_SIG_DIR = "_CodeSignature"
_RESOURCES = "CodeResources"
_INFO = "Info.plist"
_CHUNK = 1024 * 1024
_DEFAULT_WEIGHT = 1.0


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    bad: tuple[str, ...]
    bundles_checked: int


def _sha256(path: str) -> str | None:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _load_plist(path: str) -> dict | None:
    try:
        with open(path, "rb") as handle:
            data = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError, ExpatError):
        return None
    return data if isinstance(data, dict) else None


def _is_bundle(directory: str) -> bool:
    return os.path.isfile(os.path.join(directory, _SIG_DIR, _RESOURCES))


def _omit_rules(rules: object) -> list[tuple[re.Pattern[str], float, bool]]:
    parsed = []
    for pattern, rule in rules.items() if isinstance(rules, dict) else ():
        spec = rule if isinstance(rule, dict) else {}
        try:
            compiled = re.compile(pattern)
        except re.error:
            continue
        weight = spec.get("weight", _DEFAULT_WEIGHT)
        if not isinstance(weight, (int, float)):
            weight = _DEFAULT_WEIGHT
        parsed.append((compiled, float(weight), spec.get("omit") is True))
    return parsed


def _is_omitted(rel: str, rules: list[tuple[re.Pattern[str], float, bool]]) -> bool:
    matches = [(weight, omit) for pattern, weight, omit in rules if pattern.search(rel)]
    return max(matches)[1] if matches else False


def _bundle_files(bundle: str) -> list[str]:
    found = []
    for current, dirs, files in os.walk(bundle):
        rel_dir = os.path.relpath(current, bundle)
        if rel_dir == ".":
            dirs[:] = [d for d in dirs if d != _SIG_DIR]
        dirs[:] = [d for d in dirs if not _is_bundle(os.path.join(current, d))]
        for name in files:
            rel = name if rel_dir == "." else os.path.join(rel_dir, name)
            found.append(rel.replace(os.sep, "/"))
    return found


def _sealed_mismatches(bundle: str, files2: dict) -> list[str]:
    bad = []
    for rel, entry in files2.items():
        expected = entry.get("hash2") if isinstance(entry, dict) else None
        if not isinstance(expected, bytes):
            continue
        actual = _sha256(os.path.join(bundle, *rel.split("/")))
        if actual != expected.hex():
            bad.append(rel)
    return bad


def _unsealed(bundle: str, seal: dict, files2: dict) -> list[str]:
    info = _load_plist(os.path.join(bundle, _INFO)) or {}
    executable = info.get("CFBundleExecutable")
    rules = _omit_rules(seal.get("rules2"))
    return [
        rel
        for rel in _bundle_files(bundle)
        if rel not in files2 and rel != executable and not _is_omitted(rel, rules)
    ]


def _check_bundle(bundle: str) -> list[str]:
    seal = _load_plist(os.path.join(bundle, _SIG_DIR, _RESOURCES))
    files2 = seal.get("files2") if seal is not None else None
    if not isinstance(files2, dict):
        return [f"{_SIG_DIR}/{_RESOURCES}"]
    return _sealed_mismatches(bundle, files2) + _unsealed(bundle, seal, files2)


def _bundles(root: str) -> list[str]:
    found = []
    for current, dirs, _ in os.walk(root):
        dirs[:] = [d for d in dirs if d != _SIG_DIR]
        if _is_bundle(current):
            found.append(current)
    return found


def verify_bundle(app_dir: Path) -> VerifyResult:
    root = long_path(app_dir)
    bundles = _bundles(root)
    if root not in bundles:
        return VerifyResult(False, (f"{_SIG_DIR}/{_RESOURCES}",), len(bundles))
    bad: list[str] = []
    for bundle in bundles:
        prefix = os.path.relpath(bundle, root).replace(os.sep, "/")
        for rel in _check_bundle(bundle):
            bad.append(rel if prefix == "." else f"{prefix}/{rel}")
    return VerifyResult(not bad, tuple(bad), len(bundles))
