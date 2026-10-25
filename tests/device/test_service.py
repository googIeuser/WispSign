import builtins

import pytest

from wispsign.device.service import DeviceInfo, DeviceService
from wispsign.errors import WispError

APPS = {
    "com.example.demo": {
        "CFBundleDisplayName": "Demo App",
        "CFBundleShortVersionString": "1.2",
        "SignerIdentity": "Apple Development: Demo",
        "Entitlements": {
            "application-identifier": "ABCDE12345.com.example.demo",
            "aps-environment": "development",
        },
    },
    "com.example.alpha": {
        "CFBundleName": "Alpha",
        "CFBundleShortVersionString": "3.0",
        "Entitlements": {"application-identifier": "ZZZ.com.example.alpha"},
    },
}


class FakeBackend:
    def __init__(self):
        self.uninstalled = []

    def list_devices(self):
        return [DeviceInfo("U1", "Demo iPhone", "27.2", "iPhone17,1")]

    def install(self, ipa, udid, progress_cb):
        for p in (10, 50, 50, 90, 100):
            progress_cb(p)

    def browse(self, udid):
        return APPS

    def uninstall(self, bundle_id, udid):
        self.uninstalled.append((bundle_id, udid))


@pytest.fixture
def fake_backend():
    return FakeBackend()


@pytest.fixture
def failing_backend_factory():
    def make(raised: str):
        name, _, msg = raised.partition(": ")
        cls = getattr(builtins, name, None) or type(name, (Exception,), {})

        class Failing(FakeBackend):
            def _boom(self, *a, **k):
                raise cls(msg)

            list_devices = install = browse = uninstall = _boom

        return Failing()

    return make


def test_list_devices(fake_backend):
    assert DeviceService(fake_backend).list_devices()[0].udid == "U1"


def test_list_apps_extracts_push(fake_backend):
    apps = DeviceService(fake_backend).list_apps("U1")
    assert [a.name for a in apps] == ["Alpha", "Demo App"]
    demo = apps[1]
    assert demo.has_push and demo.app_id == "com.example.demo"
    assert demo.signer == "Apple Development: Demo" and demo.version == "1.2"
    assert not apps[0].has_push and apps[0].signer is None


def test_install_reports_progress(fake_backend, tmp_path):
    seen: list[int] = []
    DeviceService(fake_backend).install(tmp_path / "a.ipa", "U1", seen.append)
    assert seen == sorted(seen) and seen[-1] == 100


def test_uninstall_delegates(fake_backend):
    DeviceService(fake_backend).uninstall("com.x", "U1")
    assert fake_backend.uninstalled == [("com.x", "U1")]


@pytest.mark.parametrize(
    "raised,code",
    [
        ("ConnectionFailedToUsbmuxdError", "error.usbmux_missing"),
        ("MismatchedApplicationIdentifierEntitlement", "error.identifier_mismatch"),
        ("PasswordRequiredError", "error.device_untrusted"),
        ("ConnectionAbortedError: device disconnected", "error.device_disconnected"),
    ],
)
def test_install_maps_device_errors(raised, code, failing_backend_factory, tmp_path):
    with pytest.raises(WispError) as ei:
        DeviceService(failing_backend_factory(raised)).install(
            tmp_path / "a.ipa", "U1", lambda p: None
        )
    assert ei.value.code == code


def test_list_methods_map_errors(failing_backend_factory):
    svc = DeviceService(failing_backend_factory("NoDeviceConnectedError"))
    for call in (
        svc.list_devices,
        lambda: svc.list_apps("U1"),
        lambda: svc.uninstall("x", "U1"),
    ):
        with pytest.raises(WispError) as ei:
            call()
        assert ei.value.code == "error.no_device"


@pytest.mark.parametrize("ents", [None, [], "x", ["aps-environment"], 5])
def test_list_apps_tolerates_malformed_entitlements(fake_backend, ents):
    info = {"CFBundleDisplayName": "Odd"}
    if ents is not None:
        info["Entitlements"] = ents
    fake_backend.browse = lambda udid: {"com.odd": info}
    (app,) = DeviceService(fake_backend).list_apps("U1")
    assert app.name == "Odd" and not app.has_push and app.app_id is None


def test_list_apps_skips_non_dict_info(fake_backend):
    fake_backend.browse = lambda udid: {"bad": "str", "worse": None, **APPS}
    names = [a.name for a in DeviceService(fake_backend).list_apps("U1")]
    assert names == ["Alpha", "Demo App"]


def test_pmd3_list_devices_skips_failing_device(monkeypatch):
    from types import SimpleNamespace

    from pymobiledevice3 import usbmux

    from wispsign.device.service import Pmd3Backend

    devs = [
        SimpleNamespace(serial="BAD", connection_type="USB"),
        SimpleNamespace(serial="OK", connection_type="USB"),
    ]

    async def fake_list():
        return devs

    class FakeLd:
        all_values = {  # noqa: RUF012
            "UniqueDeviceID": "OK",
            "DeviceName": "n",
            "ProductVersion": "27.2",
            "ProductType": "iPhone",
        }

        async def close(self):
            pass

    async def fake_lockdown(udid):
        if udid == "BAD":
            raise PermissionError("untrusted")
        return FakeLd()

    monkeypatch.setattr(usbmux, "list_devices", fake_list)
    monkeypatch.setattr(Pmd3Backend, "_lockdown", staticmethod(fake_lockdown))
    assert [d.udid for d in Pmd3Backend().list_devices()] == ["OK"]
