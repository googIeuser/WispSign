import pytest

from wispsign.paths import AppPaths


@pytest.fixture
def tmp_paths(tmp_path):
    paths = AppPaths(tmp_path / "WispSign")
    paths.ensure()
    return paths
