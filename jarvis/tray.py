from __future__ import annotations

from pathlib import Path
from shutil import which
import os
import subprocess
import sys


def build_tray_command(socket_path: str, settings_path: str, apps_path: str, log_path: str) -> list[str]:
    python_cmd = sys.executable
    status_cmd = f"{python_cmd} -m jarvis ctl status --socket-path {socket_path}"
    pause_cmd = f"{python_cmd} -m jarvis ctl pause --socket-path {socket_path}"
    resume_cmd = f"{python_cmd} -m jarvis ctl resume --socket-path {socket_path}"
    reload_cmd = f"{python_cmd} -m jarvis ctl reload --socket-path {socket_path}"
    stop_cmd = f"{python_cmd} -m jarvis ctl stop --socket-path {socket_path}"
    menu = (
        f"Status!{status_cmd}|"
        f"Pause listening!{pause_cmd}|"
        f"Resume listening!{resume_cmd}|"
        f"Reload config!{reload_cmd}|"
        f"Open settings!xdg-open {settings_path}|"
        f"Open apps!xdg-open {apps_path}|"
        f"Show log!xdg-open {log_path}|"
        f"Exit!{stop_cmd}"
    )
    return [
        "yad",
        "--notification",
        "--image=audio-input-microphone",
        "--text=Jarvis",
        f"--command={status_cmd}",
        f"--menu={menu}",
    ]


def spawn_tray(socket_path: str, settings_path: str, apps_path: str, log_path: str) -> subprocess.Popen[bytes] | None:
    if which("yad") is None or not os.environ.get("DISPLAY"):
        return None
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        build_tray_command(socket_path, settings_path, apps_path, log_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
