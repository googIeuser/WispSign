pass

from dataclasses import dataclass
from datetime import datetime

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from wispsign.errors import WispError


@dataclass(frozen=True)
class P12Info:
    common_name: str
    serial: str
    team_id: str | None
    expires: datetime
    fingerprint: str


def _attr(name, oid) -> str | None:
    attrs = name.get_attributes_for_oid(oid)
    return str(attrs[0].value) if attrs else None


def load_p12(data: bytes, password: str) -> P12Info:
    try:
        key, cert, _ = pkcs12.load_key_and_certificates(data, password.encode())
    except ValueError:

        raise WispError("error.p12_password") from None
    except UnsupportedAlgorithm:
        raise WispError("error.p12_unsupported") from None
    if key is None or cert is None:
        raise WispError("error.p12_no_key")
    subject = cert.subject
    return P12Info(
        common_name=_attr(subject, NameOID.COMMON_NAME) or "",
        serial=format(cert.serial_number, "X"),
        team_id=_attr(subject, NameOID.ORGANIZATIONAL_UNIT_NAME)
        or _attr(subject, NameOID.USER_ID),
        expires=cert.not_valid_after_utc,
        fingerprint=cert.fingerprint(hashes.SHA256()).hex(),
    )
