import pytest

from wispsign.errors import ERROR_CODES, WispError, map_error


@pytest.mark.parametrize(
    "text,code",
    [
        (
            "MismatchedApplicationIdentifierEntitlement (Upgrade's application-identifier ...)",
            "error.identifier_mismatch",
        ),
        (
            "ApplicationVerificationFailed ... 0xe8008017 (A signed resource has been added, modified, or deleted.)",
            "error.signature_invalid",
        ),
        ("NoDeviceConnectedError", "error.no_device"),
        ("ConnectionFailedToUsbmuxdError", "error.usbmux_missing"),
        ("PasswordRequiredError", "error.device_untrusted"),
        ("Invalid password or PKCS12 data", "error.p12_password"),
        ("ConnectionAbortedError: device disconnected", "error.device_disconnected"),
        ("ConnectionResetError: reset", "error.device_disconnected"),
        ("BrokenPipeError: pipe", "error.device_disconnected"),
    ],
)
def test_map_known_errors(text, code):
    assert map_error(RuntimeError(text)).code == code


def _named(name: str) -> type[Exception]:
    return type(name, (Exception,), {})


@pytest.mark.parametrize(
    "name",
    [
        "PairingDialogResponsePendingError",
        "NotPairedError",
        "UserDeniedPairingError",
        "PasswordRequiredError",
    ],
)
def test_pairing_exceptions_map_to_untrusted(name):

    assert map_error(_named(name)()).code == "error.device_untrusted"


def test_verify_failed_is_a_registered_code():
    assert "error.verify_failed" in ERROR_CODES


def test_map_unknown_keeps_detail():
    e = map_error(ValueError("boom"))
    assert e.code == "error.unknown" and "boom" in e.detail


def test_wisp_error_passes_through_unchanged():
    original = WispError("error.no_device", "x", udid="abc")
    assert map_error(original) is original
    assert original.params == {"udid": "abc"}
    assert original.detail == "x"


def test_every_mappable_code_is_listed():
    for code in (
        "error.identifier_mismatch",
        "error.signature_invalid",
        "error.no_device",
        "error.usbmux_missing",
        "error.device_untrusted",
        "error.device_disconnected",
        "error.p12_password",
        "error.unknown",
        "error.secret_unreadable",
    ):
        assert code in ERROR_CODES
    assert len(set(ERROR_CODES)) == len(ERROR_CODES)
