import plistlib
import struct

import pytest
from appgen import make_app
from certgen import make_pair

from wispsign.certs.profile import parse_profile
from wispsign.errors import WispError


def signed_image(entitlements, endian="<", bits=64):
    xml = plistlib.dumps(entitlements)
    blob = struct.pack(">II", 0xFADE7171, len(xml) + 8) + xml
    signature = struct.pack(">IIIII", 0xFADE0CC0, 20 + len(blob), 1, 5, 20) + blob
    magic = 0xFEEDFACF if bits == 64 else 0xFEEDFACE
    header = struct.pack(endian + "7I", magic, 12, 0, 2, 1, 16, 0)
    if bits == 64:
        header += b"\0" * 4
    command = struct.pack(endian + "4I", 0x1D, 16, len(header) + 16, len(signature))
    return header + command + signature


def fat_image(images, endian=">", bits=32):
    magic = 0xCAFEBABE if bits == 32 else 0xCAFEBABF
    stride = 20 if bits == 32 else 32
    offset = 8 + stride * len(images)
    headers = []
    for image in images:
        values = (12, 0, offset, len(image), 0)
        headers.append(
            struct.pack(endian + "5I", *values)
            if bits == 32
            else struct.pack(endian + "IIQQII", *values, 0)
        )
        offset += len(image)
    return struct.pack(endian + "II", magic, len(images)) + b"".join(headers + images)


@pytest.mark.parametrize("endian,bits", [("<", 32), (">", 32), ("<", 64), (">", 64)])
def test_reads_embedded_entitlements_from_thin_macho(tmp_path, endian, bits):
    from wispsign.signing.entitlements import read_entitlements

    path = tmp_path / "app"
    path.write_bytes(signed_image({"aps-environment": "production"}, endian, bits))
    assert read_entitlements(path) == ({"aps-environment": "production"},)


@pytest.mark.parametrize("endian,bits", [("<", 32), (">", 32), ("<", 64), (">", 64)])
def test_reads_every_universal_slice(tmp_path, endian, bits):
    from wispsign.signing.entitlements import read_entitlements

    path = tmp_path / "app"
    path.write_bytes(
        fat_image(
            [
                signed_image({"aps-environment": "production"}),
                signed_image({"aps-environment": "development"}),
            ],
            endian,
            bits,
        )
    )
    assert read_entitlements(path) == (
        {"aps-environment": "production"},
        {"aps-environment": "development"},
    )


@pytest.mark.parametrize(
    "image",
    [
        b"not a Mach-O",
        signed_image({})[:40],
        signed_image([]),
        signed_image({}).replace(struct.pack(">I", 0xFADE7171), b"BAD!"),
        fat_image([signed_image({}), b"unsigned slice"]),
    ],
)
def test_rejects_missing_or_malformed_signed_entitlements(tmp_path, image):
    from wispsign.signing.entitlements import read_entitlements

    path = tmp_path / "app"
    path.write_bytes(image)
    with pytest.raises(WispError) as err:
        read_entitlements(path)
    assert err.value.code == "error.entitlements_invalid"


def test_rejects_entitlement_offsets_outside_the_signature(tmp_path):
    from wispsign.signing.entitlements import read_entitlements

    image = bytearray(signed_image({"aps-environment": "production"}))
    struct.pack_into(">I", image, 48 + 16, 0xFFFFFF00)
    path = tmp_path / "app"
    path.write_bytes(image)
    with pytest.raises(WispError) as err:
        read_entitlements(path)
    assert err.value.code == "error.entitlements_invalid"


def test_rejects_a_malformed_signed_application_identifier(tmp_path):
    from wispsign.signing.entitlements import verify_entitlements

    app = make_app(tmp_path, with_appex=False)
    (app / "Test").write_bytes(signed_image({"application-identifier": []}))
    profile = parse_profile(make_pair()[1])
    with pytest.raises(WispError) as err:
        verify_entitlements(app, profile)
    assert err.value.code == "error.entitlements_invalid"


def test_push_must_match_in_every_architecture(tmp_path):
    from wispsign.signing.entitlements import verify_entitlements

    app = make_app(tmp_path, with_appex=False)
    identity = {"application-identifier": "TEAM123456.com.test.app"}
    (app / "Test").write_bytes(
        fat_image(
            [
                signed_image({**identity, "aps-environment": "production"}),
                signed_image({**identity, "aps-environment": "development"}),
            ]
        )
    )
    profile = parse_profile(make_pair(app_id="com.test.app", push=True)[1])
    with pytest.raises(WispError) as err:
        verify_entitlements(app, profile)
    assert err.value.code == "error.entitlements_invalid"
