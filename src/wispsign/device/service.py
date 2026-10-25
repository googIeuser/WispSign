"""Device service: wraps pymobiledevice3 behind a small injectable backend."""

import asyncio
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from wispsign.errors import map_error

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceInfo:
    udid: str
    name: str
    ios: str
    model: str


@dataclass(frozen=True)
class InstalledApp:
    bundle_id: str
    name: str
    version: str
    signer: str | None
    has_push: bool
    app_id: str | None  # application-identifier entitlement without the team prefix


class DeviceBackend(Protocol):
    def list_devices(self) -> list[DeviceInfo]: ...

    def install(
        self, ipa: Path, udid: str, progress_cb: Callable[[int], None]
    ) -> None: ...

    def browse(self, udid: str) -> dict[str, dict[str, Any]]: ...

    def uninstall(self, bundle_id: str, udid: str) -> None: ...


async def _aw(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class Pmd3Backend:
    """pymobiledevice3-backed implementation; each call runs its own event loop."""

    def list_devices(self) -> list[DeviceInfo]:
        return asyncio.run(self._list_devices())

    def install(self, ipa: Path, udid: str, progress_cb: Callable[[int], None]) -> None:
        asyncio.run(
            self._with_proxy(
                udid, lambda p: p.install_from_local(ipa, handler=progress_cb)
            )
        )

    def browse(self, udid: str) -> dict[str, dict[str, Any]]:
        return asyncio.run(
            self._with_proxy(udid, lambda p: p.get_apps(application_type="User"))
        )

    def uninstall(self, bundle_id: str, udid: str) -> None:
        asyncio.run(self._with_proxy(udid, lambda p: p.uninstall(bundle_id)))

    async def _list_devices(self) -> list[DeviceInfo]:
        from pymobiledevice3 import usbmux

        found: list[DeviceInfo] = []
        for dev in await _aw(usbmux.list_devices()):
            if dev.connection_type != "USB":
                continue
            try:
                ld = await self._lockdown(dev.serial)
            except Exception:  # noqa: BLE001 - untrusted device: skip it, keep the rest
                _log.warning(
                    "lockdown connect failed for %s", dev.serial, exc_info=True
                )
                continue
            try:
                v = ld.all_values
                found.append(
                    DeviceInfo(
                        udid=v.get("UniqueDeviceID") or dev.serial,
                        name=v.get("DeviceName", ""),
                        ios=v.get("ProductVersion", ""),
                        model=v.get("ProductType", ""),
                    )
                )
            finally:
                await _aw(ld.close())
        return found

    @staticmethod
    async def _lockdown(udid: str) -> Any:
        from pymobiledevice3.lockdown import create_using_usbmux

        return await _aw(create_using_usbmux(serial=udid))

    async def _with_proxy(self, udid: str, action: Callable[[Any], Any]) -> Any:
        from pymobiledevice3.services.installation_proxy import InstallationProxyService

        ld = await self._lockdown(udid)
        try:
            return await _aw(action(InstallationProxyService(lockdown=ld)))
        finally:
            await _aw(ld.close())


def _to_app(bundle_id: str, info: Any) -> InstalledApp | None:
    if not isinstance(info, dict):
        return None
    ents = info.get("Entitlements")
    if not isinstance(ents, dict):
        ents = {}
    full_id = ents.get("application-identifier")
    app_id = (
        full_id.split(".", 1)[1]
        if isinstance(full_id, str) and "." in full_id
        else None
    )
    return InstalledApp(
        bundle_id=bundle_id,
        name=str(
            info.get("CFBundleDisplayName") or info.get("CFBundleName") or bundle_id
        ),
        version=str(
            info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""
        ),
        signer=info.get("SignerIdentity") or None,
        has_push="aps-environment" in ents,
        app_id=app_id,
    )


class DeviceService:
    def __init__(self, backend: DeviceBackend | None = None):
        self._backend: DeviceBackend = backend or Pmd3Backend()

    def list_devices(self) -> list[DeviceInfo]:
        try:
            return self._backend.list_devices()
        except Exception as exc:
            raise map_error(exc) from exc

    def install(self, ipa: Path, udid: str, on_progress: Callable[[int], None]) -> None:
        try:
            self._backend.install(ipa, udid, on_progress)
        except Exception as exc:
            raise map_error(exc) from exc

    def list_apps(self, udid: str) -> list[InstalledApp]:
        try:
            raw = self._backend.browse(udid)
            converted = [_to_app(bid, info) for bid, info in raw.items()]
        except Exception as exc:
            raise map_error(exc) from exc
        apps = [a for a in converted if a is not None]
        return sorted(apps, key=lambda a: a.name.casefold())

    def uninstall(self, bundle_id: str, udid: str) -> None:
        try:
            self._backend.uninstall(bundle_id, udid)
        except Exception as exc:
            raise map_error(exc) from exc
