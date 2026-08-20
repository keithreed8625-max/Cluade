"""Command line entry point: `iphone-tk <command>`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

from . import __version__, control, read
from .bridge.server import generate_token, serve_async
from .connect import automation_provider, connect, list_devices, summarize
from .errors import IphoneTkError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iphone-tk",
        description="Read from, receive from, and automate an iPhone over USB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Commands marked [dev] need Developer Mode on the phone, and on\n"
            "iOS 17+ also a tunnel: run `pymobiledevice3 remote tunneld` in a\n"
            "separate Administrator terminal and leave it open."
        ),
    )
    parser.add_argument("--version", action="version", version=f"iphone-tk {__version__}")
    parser.add_argument("--udid", help="Target a specific device when several are plugged in.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="List connected iPhones.")
    sub.add_parser("info", help="Show device identity, iOS version and storage.")
    sub.add_parser("battery", help="Show battery level and health.")

    apps = sub.add_parser("apps", help="List installed apps.")
    apps.add_argument("--all", action="store_true", help="Include Apple's built-in apps.")

    media_ls = sub.add_parser("media-ls", help="List the camera roll.")
    media_ls.add_argument("--dir", default="/DCIM", help="Remote directory (default: /DCIM).")

    pull = sub.add_parser("pull-media", help="Copy photos and videos to this PC.")
    pull.add_argument("dest", type=Path, help="Local destination folder.")
    pull.add_argument("--dir", default="/DCIM", help="Remote directory (default: /DCIM).")
    pull.add_argument("--match", help=r"Regex filter on filenames, e.g. '\.HEIC$'.")

    crash = sub.add_parser("pull-crashes", help="Copy crash logs to this PC.")
    crash.add_argument("dest", type=Path)

    syslog = sub.add_parser("syslog", help="Capture live system log lines.")
    syslog.add_argument("dest", type=Path, help="File to write.")
    syslog.add_argument("--lines", type=int, default=200, help="Stop after N lines.")
    syslog.add_argument("--contains", help="Keep only lines containing this text.")

    backup = sub.add_parser("backup", help="Full iTunes-format backup (slow, large).")
    backup.add_argument("dest", type=Path)

    launch = sub.add_parser("launch", help="[dev] Launch an app by bundle id.")
    launch.add_argument("bundle_id")

    kill = sub.add_parser("kill", help="[dev] Kill an app by bundle id.")
    kill.add_argument("bundle_id")

    sub.add_parser("ps", help="[dev] List running processes.")

    shot = sub.add_parser("screenshot", help="[dev] Capture the screen to a PNG.")
    shot.add_argument("dest", type=Path, nargs="?", default=Path("screenshot.png"))

    loc = sub.add_parser("set-location", help="[dev] Spoof the device's GPS position.")
    loc.add_argument("latitude", type=float)
    loc.add_argument("longitude", type=float)

    sub.add_parser("clear-location", help="[dev] Restore the real GPS position.")

    bridge = sub.add_parser("bridge", help="Receive files and text sent from the phone.")
    bridge.add_argument("--inbox", type=Path, default=Path("inbox"), help="Where uploads land.")
    bridge.add_argument("--port", type=int, default=8765)
    bridge.add_argument("--host", default="0.0.0.0", help="0.0.0.0 exposes it to your LAN.")
    bridge.add_argument("--token", help="Shared secret. Generated and printed if omitted.")

    return parser


async def run(args: argparse.Namespace) -> int:
    command = args.command

    if command == "devices":
        udids = await list_devices()
        if not udids:
            print("No iPhone connected.")
            return 1
        for udid in udids:
            print(udid)
        return 0

    if command == "bridge":
        # Runs without a device: the phone reaches in over the network instead.
        token = args.token or generate_token()
        print(f"Inbox: {Path(args.inbox).resolve()}")
        print(f"Token: {token}")
        print(f"Listening on port {args.port}. From the phone, POST to:")
        print(f"  http://<this-pc-lan-ip>:{args.port}/upload")
        print("Find the LAN IP with `ipconfig` (IPv4 Address on your Wi-Fi adapter).")
        print("Ctrl-C to stop.\n")
        await serve_async(Path(args.inbox), token, host=args.host, port=args.port)
        return 0

    if command in _AUTOMATION_COMMANDS:
        async with automation_provider(args.udid) as provider:
            return await _run_automation(command, args, provider)

    lockdown = await connect(args.udid)
    try:
        return await _run_lockdown(command, args, lockdown)
    finally:
        await lockdown.close()


_AUTOMATION_COMMANDS = frozenset(
    {"launch", "kill", "ps", "screenshot", "set-location", "clear-location"}
)


async def _run_automation(command: str, args: argparse.Namespace, provider: Any) -> int:
    if command == "launch":
        print(f"Launched {args.bundle_id} as pid {await control.launch_app(provider, args.bundle_id)}")
    elif command == "kill":
        pid = await control.kill_app(provider, args.bundle_id)
        print(f"Killed pid {pid}" if pid else f"{args.bundle_id} was not running.")
    elif command == "ps":
        for process in await control.processes(provider):
            print(f"{process.get('pid', '?'):>6}  {process.get('name', '')}")
    elif command == "screenshot":
        print(f"Wrote {await control.screenshot(provider, args.dest)}")
    elif command == "set-location":
        await control.set_location(provider, args.latitude, args.longitude)
        print(f"Location set to {args.latitude}, {args.longitude}. Run clear-location to undo.")
    elif command == "clear-location":
        await control.clear_location(provider)
        print("Real GPS restored.")
    return 0


async def _run_lockdown(command: str, args: argparse.Namespace, lockdown: Any) -> int:
    if command == "info":
        print((await summarize(lockdown)).describe())
        print()
        print(read.dumps(await read.device_info(lockdown)))
    elif command == "battery":
        print(read.dumps(await control.battery(lockdown)))
    elif command == "apps":
        for app in await read.list_apps(lockdown, user_only=not args.all):
            print(f"{app['bundle_id']:<50} {app['name']} {app['version']}")
    elif command == "media-ls":
        for name in await read.list_media(lockdown, args.dir):
            print(name)
    elif command == "pull-media":
        print(f"Copied into {await read.pull_media(lockdown, args.dest, args.dir, args.match)}")
    elif command == "pull-crashes":
        print(f"Copied into {await read.pull_crash_reports(lockdown, args.dest)}")
    elif command == "syslog":
        print(f"Capturing {args.lines} lines... (Ctrl-C to stop early)")
        print(f"Wrote {await read.capture_syslog(lockdown, args.dest, args.lines, args.contains)}")
    elif command == "backup":
        print("Backing up. This takes a long time and cannot be safely interrupted.")
        print(f"Backup written to {await read.backup(lockdown, args.dest)}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(run(args))
    except IphoneTkError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
