"""Goal 1: pull data off the phone.

Every function here goes over plain lockdown, so none of it needs Developer Mode,
a tunnel, or Administrator rights — only a trusted USB connection.
"""

from __future__ import annotations

import json
import plistlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider
from pymobiledevice3.services.afc import AfcService
from pymobiledevice3.services.crash_reports import CrashReportsManager
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service
from pymobiledevice3.services.os_trace import OsTraceService

# The media partition AFC exposes without any entitlement. DCIM is the camera roll.
MEDIA_ROOT = "/"
CAMERA_ROLL = "/DCIM"

# Keys worth reporting from lockdown's value store, in print order.
INFO_KEYS = (
    "DeviceName",
    "ProductType",
    "ProductVersion",
    "BuildVersion",
    "UniqueDeviceID",
    "SerialNumber",
    "WiFiAddress",
    "BluetoothAddress",
    "TotalDiskCapacity",
    "TimeIntervalSince1970",
)


async def device_info(lockdown: LockdownServiceProvider) -> dict[str, Any]:
    """Collect the lockdown values that describe the device."""
    info: dict[str, Any] = {}
    for key in INFO_KEYS:
        try:
            value = await lockdown.get_value(key=key)
        except Exception:
            continue
        info[key] = _jsonable(value)
    return info


async def list_apps(
    lockdown: LockdownServiceProvider, user_only: bool = True
) -> list[dict[str, Any]]:
    """List installed apps.

    :param user_only: Exclude Apple's built-ins, which otherwise bury your own apps.
    """
    service = InstallationProxyService(lockdown)
    try:
        apps = await service.get_apps(application_type="User" if user_only else "Any")
    finally:
        await _close(service)

    listing = [
        {
            "bundle_id": bundle_id,
            "name": app.get("CFBundleDisplayName") or app.get("CFBundleName") or bundle_id,
            "version": app.get("CFBundleShortVersionString", ""),
            "path": app.get("Path", ""),
        }
        for bundle_id, app in apps.items()
    ]
    listing.sort(key=lambda entry: entry["name"].lower())
    return listing


def _afc(lockdown: LockdownServiceProvider) -> AfcService:
    return AfcService(lockdown)


async def list_media(lockdown: LockdownServiceProvider, remote_dir: str = CAMERA_ROLL) -> list[str]:
    """List a directory on the media partition (the camera roll by default)."""
    afc = _afc(lockdown)
    try:
        return afc.listdir(remote_dir)
    finally:
        await _close(afc)


async def pull_media(
    lockdown: LockdownServiceProvider,
    dest: Path,
    remote_dir: str = CAMERA_ROLL,
    pattern: Optional[str] = None,
) -> Path:
    """Copy files off the media partition into `dest`.

    :param pattern: Regex applied to filenames, e.g. `r"\\.HEIC$"` for photos only.
    """
    dest.mkdir(parents=True, exist_ok=True)
    afc = _afc(lockdown)
    try:
        await afc.pull(
            remote_dir,
            str(dest),
            match=re.compile(pattern) if pattern else None,
            ignore_errors=True,
        )
    finally:
        await _close(afc)
    return dest


async def pull_crash_reports(lockdown: LockdownServiceProvider, dest: Path) -> Path:
    """Copy crash logs off the device, leaving the originals in place."""
    dest.mkdir(parents=True, exist_ok=True)
    manager = CrashReportsManager(lockdown)
    try:
        await manager.pull(str(dest), erase=False)
    finally:
        await _close(manager)
    return dest


async def capture_syslog(
    lockdown: LockdownServiceProvider,
    dest: Path,
    limit: int = 200,
    contains: Optional[str] = None,
) -> Path:
    """Stream the live system log until `limit` matching lines are written.

    The device emits continuously, so this stops on a count rather than on EOF.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    service = OsTraceService(lockdown)
    written = 0
    try:
        with dest.open("w", encoding="utf-8", errors="replace") as handle:
            async for entry in service.syslog():
                line = _format_syslog(entry)
                if contains and contains.lower() not in line.lower():
                    continue
                handle.write(line + "\n")
                written += 1
                if written >= limit:
                    break
    finally:
        await _close(service)
    return dest


def _format_syslog(entry: Any) -> str:
    timestamp = getattr(entry, "timestamp", None) or datetime.now(timezone.utc)
    return (
        f"{timestamp} {getattr(entry, 'label', '') or ''} "
        f"[{getattr(entry, 'pid', '?')}] {getattr(entry, 'message', entry)}"
    ).strip()


async def backup(lockdown: LockdownServiceProvider, dest: Path, full: bool = True) -> Path:
    """Run a real iTunes-format backup into `dest`.

    This is the only route to data apps keep private (Messages, Health, app
    databases). It is slow and large; budget the size of the phone's used space.
    Encrypted-backup devices need the password set on the phone, not here.
    """
    dest.mkdir(parents=True, exist_ok=True)
    service = Mobilebackup2Service(lockdown)
    try:
        await service.backup(full=full, backup_directory=str(dest))
    finally:
        await _close(service)
    return dest


async def _close(service: Any) -> None:
    """Close a service whether it exposes close(), aclose(), or neither."""
    for name in ("aclose", "close"):
        closer = getattr(service, name, None)
        if closer is None:
            continue
        try:
            result = closer()
            if hasattr(result, "__await__"):
                await result
        except Exception:
            pass
        return


def _jsonable(value: Any) -> Any:
    """Coerce plist scalars into something json.dumps will accept."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, plistlib.UID):
        return int(value.data)
    return value


def dumps(payload: Any) -> str:
    """Serialize plist-derived data, coercing the types json refuses."""
    return json.dumps(_jsonable(payload), indent=2, sort_keys=False, default=str)
