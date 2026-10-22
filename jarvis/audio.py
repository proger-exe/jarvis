from __future__ import annotations

from dataclasses import dataclass
from shutil import which
from subprocess import PIPE, DEVNULL, Popen
from typing import Iterable
import subprocess

from jarvis.config import AudioConfig


@dataclass(slots=True)
class AudioDevice:
    index: str
    name: str
    driver: str
    format: str
    state: str

    @property
    def is_monitor(self) -> bool:
        return self.name.endswith(".monitor")

    @property
    def is_usb(self) -> bool:
        return ".usb-" in self.name


def list_sources() -> list[AudioDevice]:
    if which("pactl") is None:
        return []
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    devices = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        devices.append(
            AudioDevice(
                index=parts[0],
                name=parts[1],
                driver=parts[2],
                format=parts[3],
                state=parts[4],
            )
        )
    return devices


def pick_default_source(devices: Iterable[AudioDevice]) -> str:
    filtered = [device for device in devices if not device.is_monitor]
    if not filtered:
        return ""
    usb_sources = [device for device in filtered if device.is_usb]
    if usb_sources:
        return usb_sources[0].name
    return filtered[0].name


def resolve_source(config: AudioConfig) -> str:
    if config.source:
        return config.source
    return pick_default_source(list_sources())


def start_ffmpeg_capture(config: AudioConfig, source_name: str) -> Popen[bytes]:
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-f",
        "pulse",
        "-i",
        source_name,
        "-ar",
        str(config.sample_rate),
        "-ac",
        str(config.channels),
        "-f",
        "s16le",
        "-",
    ]
    return Popen(command, stdout=PIPE, stderr=DEVNULL)
