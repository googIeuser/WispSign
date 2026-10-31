pass

import plistlib
import secrets
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from cryptography.x509.oid import NameOID

_CA_NAME = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "WispSign Test CA")])
_CA_DAYS = 3650
_ca: list = []


def _test_ca():
    pass




    if not _ca:
        key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.now(UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(_CA_NAME)
            .issuer_name(_CA_NAME)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=_CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
            .sign(key, hashes.SHA256())
        )
        _ca.append((key, cert))
    return _ca[0]


def _make_cert(team: str, expires_days: int):
    ca_key, _ = _test_ca()
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, team),
            x509.NameAttribute(
                NameOID.COMMON_NAME, f"Apple Distribution: Test Org ({team})"
            ),
            x509.NameAttribute(NameOID.USER_ID, team),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(_CA_NAME)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=expires_days))
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def _p12(key, cert, password: str) -> bytes:
    return pkcs12.serialize_key_and_certificates(
        b"test",
        key,
        cert,
        [_test_ca()[1]],
        serialization.BestAvailableEncryption(password.encode()),
    )


def wrap_plist(plist: dict, key=None, cert=None) -> bytes:
    pass
    if key is None:
        key, cert = _make_cert("TEAM123456", 365)
    return (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(plistlib.dumps(plist))
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )


def valid_plist(**overrides) -> dict:
    pass
    plist = {
        "Name": "P",
        "UUID": "U",
        "TeamIdentifier": ["TEAM123456"],
        "ExpirationDate": datetime(2030, 1, 1),
        "Entitlements": {"application-identifier": "TEAM123456.com.a.b"},
    }
    for k, v in overrides.items():
        if v is None:
            plist.pop(k, None)
        else:
            plist[k] = v
    return plist


def make_cert_only_p12() -> tuple[bytes, str]:
    _, cert = _make_cert("TEAM123456", 365)
    password = secrets.token_hex(8)
    data = pkcs12.serialize_key_and_certificates(
        b"test",
        None,
        cert,
        None,
        serialization.BestAvailableEncryption(password.encode()),
    )
    return data, password


def make_pair(
    app_id: str = "com.test.*",
    push: bool = False,
    devices: tuple[str, ...] = ("UDID1",),
    expires_days: int = 365,
    team: str = "TEAM123456",
    all_devices: bool = False,
) -> tuple[bytes, bytes, str]:
    pass
    key, cert = _make_cert(team, expires_days)
    password = secrets.token_hex(8)
    entitlements: dict = {"application-identifier": f"{team}.{app_id}"}
    if push:
        entitlements["aps-environment"] = "production"
    plist: dict = {
        "Name": "Test Profile",
        "UUID": "00000000-0000-0000-0000-000000000001",
        "TeamIdentifier": [team],
        "ExpirationDate": datetime.now(UTC).replace(tzinfo=None)
        + timedelta(days=expires_days),
        "DeveloperCertificates": [cert.public_bytes(serialization.Encoding.DER)],
        "Entitlements": entitlements,
    }
    if devices:
        plist["ProvisionedDevices"] = list(devices)
    if all_devices:
        plist["ProvisionsAllDevices"] = True
    return _p12(key, cert, password), wrap_plist(plist, key, cert), password
