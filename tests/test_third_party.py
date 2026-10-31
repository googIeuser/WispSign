import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "third_party.py"


@pytest.fixture(scope="module")
def third_party():
    spec = importlib.util.spec_from_file_location("third_party", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _names(dists):
    return {d.metadata["Name"].lower() for d in dists}


def test_runtime_closure_is_recursive_and_skips_dev_tools(third_party):
    names = _names(third_party.runtime_closure())
    assert {"pymobiledevice3", "pywebview", "cryptography", "httpx"} <= names
    assert {"construct", "httpcore", "cffi"} <= names
    assert names.isdisjoint({"wispsign", "pytest", "pytest-cov", "ruff", "pyinstaller"})


def test_lock_pins_exact_versions(third_party):
    lines = [
        line
        for line in third_party.lock_text().splitlines()
        if not line.startswith("#")
    ]
    assert "pymobiledevice3==11.43.1" in lines
    assert all("==" in line for line in lines)


def test_committed_lock_matches_the_environment(third_party):
    committed = third_party.LOCK_FILE.read_text(encoding="utf-8")
    assert committed == third_party.lock_text(), (
        "run: python packaging/third_party.py lock"
    )


def test_notices_cover_every_bundled_package(third_party, tmp_path):
    out = tmp_path / "THIRD_PARTY_NOTICES.txt"
    assert third_party.main(["notices", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    for dist in third_party.runtime_closure():
        assert f"\n{dist.metadata['Name']} {dist.version}\n" in text
    assert "\npyinstaller " in text.lower()
    assert "\nzsign\nLicense: MIT\n" in text
    assert "Copyright © 2019, [Encode OSS Ltd]" in text or "Encode OSS" in text


def test_bad_arguments_print_usage(third_party, capsys):
    assert third_party.main(["nope"]) == 2
    assert "third_party.py lock" in capsys.readouterr().err
