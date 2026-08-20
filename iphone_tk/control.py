"""Goal 4: drive the phone from the PC.

What is actually possible, and what is not:

Possible here — Apple exposes these to development tools, so they work with
Developer Mode on (plus a tunnel on iOS 17+):
  * launch and kill apps by bundle id
  * take screenshots
  * spoof the device's GPS location
  * list running processes; reboot and shut down

NOT possible from Windows — synthetic touches and swipes. Driving the UI needs
WebDriverAgent, an Xcode project that must be compiled and code-signed on a Mac
before it can run on the phone. There is no Windows path to it. If you need
UI automation, the on-device Shortcuts app is the realistic substitute: it can
open apps, manipulate text and media, and be triggered from `bridge/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pymobiledevice3.services.diagnostics import DiagnosticsService
from pymobiledevice3.services.dvt.instruments.application_listing import ApplicationListing
from pymobiledevice3.services.dvt.instruments.device_info import DeviceInfo
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl
from pymobiledevice3.services.dvt.instruments.screenshot import Screenshot

from .errors import IphoneTkError


async def launch_app(provider: Any, bundle_id: str, kill_existing: bool = True) -> int:
    """Launch an app in the foreground and return its PID."""
    async with DvtProvider(provider) as dvt, ProcessControl(dvt) as process_control:
        return await process_control.launch(bundle_id, kill_existing=kill_existing)


async def kill_app(provider: Any, bundle_id: str) -> Optional[int]:
    """Kill an app by bundle id. Returns the PID killed, or None if not running."""
    async with DvtProvider(provider) as dvt, ProcessControl(dvt) as process_control:
        pid = await process_control.process_identifier_for_bundle_identifier(bundle_id)
        if not pid:
            return None
        await process_control.kill(pid)
        return pid


async def running_apps(provider: Any) -> list[dict[str, Any]]:
    """List apps the instruments daemon reports as installed and runnable."""
    async with DvtProvider(provider) as dvt, ApplicationListing(dvt) as listing:
        return await listing.applist()


async def processes(provider: Any) -> list[dict[str, Any]]:
    """List every running process, including system daemons."""
    async with DvtProvider(provider) as dvt, DeviceInfo(dvt) as info:
        return await info.proclist()


async def screenshot(provider: Any, dest: Path) -> Path:
    """Capture the screen as it is right now and write it to `dest` (PNG)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with DvtProvider(provider) as dvt, Screenshot(dvt) as capture:
        dest.write_bytes(await capture.get_screenshot())
    return dest


async def set_location(provider: Any, latitude: float, longitude: float) -> None:
    """Override the device's reported GPS position.

    The override holds until `clear_location`, the device reboots, or the USB
    connection drops. Every app on the phone sees the fake position.
    """
    if not -90 <= latitude <= 90:
        raise IphoneTkError(f"Latitude must be between -90 and 90, got {latitude}.")
    if not -180 <= longitude <= 180:
        raise IphoneTkError(f"Longitude must be between -180 and 180, got {longitude}.")
    async with DvtProvider(provider) as dvt, LocationSimulation(dvt) as simulation:
        await simulation.set(latitude, longitude)


async def clear_location(provider: Any) -> None:
    """Hand location control back to the real GPS."""
    async with DvtProvider(provider) as dvt, LocationSimulation(dvt) as simulation:
        await simulation.clear()


async def reboot(lockdown: Any) -> None:
    """Restart the device. Goes over lockdown, so no Developer Mode needed."""
    service = DiagnosticsService(lockdown)
    try:
        await service.restart()
    finally:
        await _close(service)


async def shutdown(lockdown: Any) -> None:
    """Power the device off. It cannot be powered back on over USB."""
    service = DiagnosticsService(lockdown)
    try:
        await service.shutdown()
    finally:
        await _close(service)


async def battery(lockdown: Any) -> dict[str, Any]:
    """Read battery level, charging state and health counters."""
    service = DiagnosticsService(lockdown)
    try:
        return await service.get_battery() or {}
    finally:
        await _close(service)


async def _close(service: Any) -> None:
    closer = getattr(service, "close", None)
    if closer is None:
        return
    try:
        result = closer()
        if hasattr(result, "__await__"):
            await result
    except Exception:
        pass
