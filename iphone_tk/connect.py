"""Device discovery and service-provider construction.

Two transports matter, and which one you get depends on the iOS version:

* **lockdown over usbmux** — works on every iOS version, no privileges needed.
  Everything under `read.py` uses this.
* **RSD over a tunnel** — required on iOS 17+ for the DVT/instruments services
  that back `control.py`. Building the tunnel creates a virtual network
  interface, so it needs Administrator rights; we do not create it ourselves.
  The user runs `pymobiledevice3 remote tunneld` as admin and we connect to it.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from pymobiledevice3 import usbmux
from pymobiledevice3.exceptions import (
    ConnectionFailedToUsbmuxdError,
    NoDeviceConnectedError,
    NotPairedError,
    PairingDialogResponsePendingError,
    UserDeniedPairingError,
)
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider

from .errors import DeveloperModeError, NoDeviceError, TrustError

from pymobiledevice3.tunneld.api import TUNNELD_DEFAULT_ADDRESS as TUNNELD_DEFAULT


@dataclass(frozen=True)
class DeviceSummary:
    """The handful of device facts worth printing before doing anything else."""

    udid: str
    name: str
    ios_version: str
    model: str
    developer_mode: Optional[bool]

    def describe(self) -> str:
        dev = {True: "on", False: "off", None: "unknown"}[self.developer_mode]
        return (
            f"{self.name} ({self.model})\n"
            f"  iOS:            {self.ios_version}\n"
            f"  UDID:           {self.udid}\n"
            f"  Developer Mode: {dev}"
        )


async def list_devices() -> list[str]:
    """Return the UDIDs of every iPhone currently reachable over USB."""
    try:
        devices = await usbmux.list_devices()
    except (ConnectionFailedToUsbmuxdError, ConnectionRefusedError, FileNotFoundError, OSError) as exc:
        # The usbmux socket is absent. On Windows this is almost always the
        # Apple Mobile Device Service being stopped or never installed.
        raise NoDeviceError(
            f"Could not reach the Apple device service ({type(exc).__name__})."
        ) from exc
    return [device.serial for device in devices]


async def connect(udid: Optional[str] = None) -> LockdownServiceProvider:
    """Open a lockdown connection, translating library errors into actionable ones.

    :param udid: Target a specific device. Omit when exactly one is plugged in.
    """
    try:
        return await create_using_usbmux(serial=udid)
    except (ConnectionFailedToUsbmuxdError, ConnectionRefusedError, FileNotFoundError) as exc:
        raise NoDeviceError(
            f"Could not reach the Apple device service ({type(exc).__name__})."
        ) from exc
    except NoDeviceConnectedError as exc:
        raise NoDeviceError() from exc
    except (NotPairedError, PairingDialogResponsePendingError, UserDeniedPairingError) as exc:
        raise TrustError() from exc


async def summarize(lockdown: LockdownServiceProvider) -> DeviceSummary:
    """Read the identifying values every command prints before it acts."""
    developer_mode: Optional[bool] = None
    try:
        developer_mode = await lockdown.get_developer_mode_status()
    except Exception:
        # Pre-iOS-16 devices have no such concept; never fail a command over it.
        developer_mode = None

    return DeviceSummary(
        udid=await _value(lockdown, "UniqueDeviceID"),
        name=await _value(lockdown, "DeviceName"),
        ios_version=await _value(lockdown, "ProductVersion"),
        model=await _value(lockdown, "ProductType"),
        developer_mode=developer_mode,
    )


async def _value(lockdown: LockdownServiceProvider, key: str) -> str:
    try:
        return str(await lockdown.get_value(key=key))
    except Exception:
        return "unknown"


def _needs_tunnel(ios_version: str) -> bool:
    """True when this iOS version routes DVT services through RSD rather than lockdown.

    Apple moved the instruments services behind RemoteXPC in iOS 17.
    """
    try:
        major = int(ios_version.split(".", 1)[0])
    except (ValueError, AttributeError):
        return False
    return major >= 17


@asynccontextmanager
async def automation_provider(
    udid: Optional[str] = None,
    tunneld: tuple[str, int] = TUNNELD_DEFAULT,
) -> AsyncIterator[Any]:
    """Yield a service provider that can reach the DVT services.

    On iOS 16 and earlier this is the plain lockdown connection. On iOS 17+ it is
    an RSD connection discovered through a running `tunneld`, and we fail with
    instructions rather than a stack trace when that daemon is not up.
    """
    lockdown = await connect(udid)
    summary = await summarize(lockdown)

    if summary.developer_mode is False:
        await lockdown.close()
        raise DeveloperModeError(f"Developer Mode is off on {summary.name}.")

    if not _needs_tunnel(summary.ios_version):
        try:
            yield lockdown
        finally:
            await lockdown.close()
        return

    rsd = await _connect_via_tunneld(summary.udid, tunneld)
    try:
        yield rsd
    finally:
        await rsd.close()
        await lockdown.close()


async def _connect_via_tunneld(udid: str, tunneld: tuple[str, int]) -> Any:
    """Find this device's tunnel in a running tunneld and open RSD against it."""
    from pymobiledevice3.tunneld.api import TunneldConnectionError, get_tunneld_device_by_udid

    try:
        rsd = await asyncio.wait_for(
            get_tunneld_device_by_udid(udid, tunneld_address=tunneld), timeout=10
        )
    except (TunneldConnectionError, ConnectionError, OSError, asyncio.TimeoutError) as exc:
        raise DeveloperModeError(
            f"iOS 17+ routes automation through a tunnel, and nothing is answering on "
            f"{tunneld[0]}:{tunneld[1]} ({type(exc).__name__})."
        ) from exc

    if rsd is None:
        raise DeveloperModeError(
            f"A tunnel daemon is running but has no tunnel for {udid}.\n"
            "Unplug and replug the phone, and confirm tunneld's terminal lists it."
        )
    return rsd


__all__ = [
    "DeviceSummary",
    "automation_provider",
    "connect",
    "list_devices",
    "summarize",
]
