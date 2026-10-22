from __future__ import annotations

from pathlib import Path
import argparse
import json
import subprocess

from jarvis.audio import list_sources, pick_default_source
from jarvis.config import load_settings
from jarvis.control import send_command
from jarvis.daemon import JarvisDaemon, run_doctor
from jarvis.tray import build_tray_command


DEFAULT_SETTINGS = "config/settings.toml"
DEFAULT_APPS = "config/apps.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS)
    parser.add_argument("--apps", default=DEFAULT_APPS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run")
    subparsers.add_parser("doctor")
    subparsers.add_parser("list-devices")
    tray = subparsers.add_parser("tray")
    tray.add_argument("--socket-path")
    ctl = subparsers.add_parser("ctl")
    ctl.add_argument("action", choices=["status", "pause", "resume", "reload", "stop"])
    ctl.add_argument("--socket-path")
    return parser


def resolve_socket_path(settings_path: str, explicit_socket_path: str | None) -> str:
    if explicit_socket_path:
        return explicit_socket_path
    return load_settings(settings_path).control.socket_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        daemon = JarvisDaemon(settings_path=args.settings, apps_path=args.apps)
        return daemon.run_forever()
    if args.command == "doctor":
        return run_doctor(settings_path=args.settings, apps_path=args.apps)
    if args.command == "list-devices":
        devices = list_sources()
        selected = pick_default_source(devices)
        for device in devices:
            marker = "*" if device.name == selected else " "
            print(f"{marker} {device.index}\t{device.name}\t{device.driver}\t{device.format}\t{device.state}")
        return 0
    if args.command == "ctl":
        response = send_command(resolve_socket_path(args.settings, args.socket_path), args.action)
        if response.state is not None:
            print(json.dumps(response.state, ensure_ascii=False, indent=2))
        else:
            print(response.message)
        return 0 if response.ok else 1
    if args.command == "tray":
        socket_path = resolve_socket_path(args.settings, args.socket_path)
        command = build_tray_command(
            socket_path=socket_path,
            settings_path=str(Path(args.settings).resolve()),
            apps_path=str(Path(args.apps).resolve()),
            log_path=str((Path("runtime") / "jarvis.log").resolve()),
        )
        return subprocess.run(command, check=False).returncode
    parser.print_help()
    return 1
