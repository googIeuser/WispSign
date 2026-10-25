"""Backend error type and mapping of raw exceptions to i18n error codes."""

import re

# Codes that exist so far; later tasks append their own.
ERROR_CODES: tuple[str, ...] = (
    "error.identifier_mismatch",
    "error.signature_invalid",
    "error.no_device",
    "error.usbmux_missing",
    "error.device_untrusted",
    "error.device_disconnected",
    "error.p12_password",
    "error.p12_no_key",
    "error.p12_unsupported",
    "error.profile_invalid",
    "error.secret_unreadable",
    "error.cert_profile_mismatch",
    "error.cert_expired",
    "error.profile_device_missing",
    "error.profile_app_id_mismatch",
    "error.cert_not_found",
    "error.cert_meta_corrupt",
    "error.repo_invalid",
    "error.url_not_https",
    "error.repo_too_large",
    "error.ipa_invalid",
    "error.ipa_too_large",
    "error.sign_failed",
    "error.verify_failed",
    "error.entitlements_invalid",
    "error.zsign_missing",
    "error.entry_not_found",
    "error.settings_invalid",
    "error.icon_invalid",
    "error.network",
    "error.io",
    "error.unknown",
)


class WispError(Exception):
    def __init__(self, code: str, detail: str = "", **params: object):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.params = params


_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), code)
    for pattern, code in (
        (r"MismatchedApplicationIdentifierEntitlement", "error.identifier_mismatch"),
        (r"ApplicationVerificationFailed|0xe8008017", "error.signature_invalid"),
        (r"NoDeviceConnectedError", "error.no_device"),
        (r"ConnectionFailedToUsbmuxdError", "error.usbmux_missing"),
        (
            (
                r"PasswordRequiredError|PairingDialogResponsePendingError"
                r"|NotPairedError|UserDeniedPairingError"
            ),
            "error.device_untrusted",
        ),
        (
            r"device disconnected|ConnectionAbortedError|ConnectionResetError|BrokenPipeError|ConnectionTerminatedError",
            "error.device_disconnected",
        ),
        (r"Invalid password or PKCS12 data", "error.p12_password"),
    )
)


def map_error(exc: BaseException) -> WispError:
    if isinstance(exc, WispError):
        return exc
    text = f"{type(exc).__name__}: {exc}"
    for pattern, code in _RULES:
        if pattern.search(text):
            return WispError(code, str(exc))
    return WispError("error.unknown", str(exc))
