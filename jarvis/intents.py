from __future__ import annotations

from dataclasses import dataclass
from shutil import which
import re
import subprocess

from jarvis.config import AppSpec


SYNONYMS = {
    "в с код": "vscode",
    "вижуал студио код": "visual studio code",
    "фаерфокс": "firefox",
}


@dataclass(slots=True)
class IntentMatch:
    app: AppSpec
    transcript: str


def normalize_text(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"[^\w\s-]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for source, target in SYNONYMS.items():
        normalized = normalized.replace(source, target)
    return normalized


def match_intent(text: str, apps: list[AppSpec]) -> IntentMatch | None:
    normalized = normalize_text(text)
    for app in apps:
        for phrase in app.phrases:
            candidate = normalize_text(phrase)
            if normalized == candidate or normalized.startswith(candidate):
                return IntentMatch(app=app, transcript=normalized)
    return None


def focus_window(process_names: list[str]) -> bool:
    if not process_names or which("wmctrl") is None:
        return False
    result = subprocess.run(
        ["wmctrl", "-lx"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    lower_targets = [name.lower() for name in process_names]
    for line in result.stdout.splitlines():
        lower_line = line.lower()
        if any(target in lower_line for target in lower_targets):
            window_id = line.split()[0]
            activate = subprocess.run(["wmctrl", "-ia", window_id], check=False)
            return activate.returncode == 0
    return False


def launch_command(command: list[str]) -> bool:
    if not command:
        return False
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


def open_url(url: str) -> bool:
    if not url:
        return False
    subprocess.Popen(
        ["xdg-open", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True
