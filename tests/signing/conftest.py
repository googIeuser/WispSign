import pytest
from appgen import make_app
from certgen import make_pair

from wispsign.certs.store import CertStore
from wispsign.signing.zsign import ZsignRunner, zsign_path


@pytest.fixture
def fake_cert(tmp_paths):
    p12, profile, password = make_pair()
    return CertStore(tmp_paths).import_pair(p12, profile, password, "Fake")


@pytest.fixture
def sign_in_place(tmp_paths, fake_cert):
    """Sign an unpacked .app where it lies, with the real zsign and the fake cert."""
    p12, profile, password = CertStore(tmp_paths).materialize(fake_cert.id)

    def sign(app):
        ZsignRunner(zsign_path()).sign(app, p12, profile, password)
        return app

    return sign


@pytest.fixture
def signed_app(tmp_path, sign_in_place):
    return sign_in_place(make_app(tmp_path / "s"))
