from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


@dataclass(slots=True)
class AudioConfig:
    source: str = ""
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 30
    vad_aggressiveness: int = 2
    silence_ms: int = 800
    min_speech_ms: int = 400

    @property
    def frame_size_bytes(self) -> int:
        return int(self.sample_rate * (self.chunk_duration_ms / 1000.0) * 2 * self.channels)


@dataclass(slots=True)
class SpeechConfig:
    language: str = "ru"
    model_path: str = "data/models/vosk-ru"


@dataclass(slots=True)
class TtsConfig:
    backend: str = "piper"
    voice_model: str = "ru_RU-irina-medium"
    voice_dir: str = "data/voices/piper"
    player: str = "paplay"
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w_scale: float = 0.8
    normalize_audio: bool = True
    volume: float = 1.0
    use_cuda: bool = False
    spd_say_engine: str = "spd-say"
    spd_say_voice: str = "ru"
    spd_say_rate: int = -20


@dataclass(slots=True)
class ControlConfig:
    socket_path: str = "/tmp/jarvis.sock"


@dataclass(slots=True)
class UiConfig:
    tray_enabled: bool = True
    notify_on_error: bool = True


@dataclass(slots=True)
class Settings:
    audio: AudioConfig = field(default_factory=AudioConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    ui: UiConfig = field(default_factory=UiConfig)


@dataclass(slots=True)
class AppSpec:
    id: str
    phrases: list[str]
    action: str
    command: list[str] = field(default_factory=list)
    url: str = ""
    process_names: list[str] = field(default_factory=list)
    response: str = ""


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_settings(path: str | Path) -> Settings:
    data = _read_toml(Path(path))
    audio = AudioConfig(**data.get("audio", {}))
    speech = SpeechConfig(**data.get("speech", {}))
    tts_data = dict(data.get("tts", {}))
    if "engine" in tts_data and "backend" not in tts_data:
        tts_data["backend"] = "spd-say"
        tts_data["spd_say_engine"] = tts_data.pop("engine")
        if "voice" in tts_data:
            tts_data["spd_say_voice"] = tts_data.pop("voice")
        if "rate" in tts_data:
            tts_data["spd_say_rate"] = tts_data.pop("rate")
    tts = TtsConfig(**tts_data)
    control = ControlConfig(**data.get("control", {}))
    ui = UiConfig(**data.get("ui", {}))
    return Settings(audio=audio, speech=speech, tts=tts, control=control, ui=ui)


def load_apps(path: str | Path) -> list[AppSpec]:
    data = _read_toml(Path(path))
    apps = []
    for entry in data.get("app", []):
        apps.append(
            AppSpec(
                id=entry["id"],
                phrases=list(entry.get("phrases", [])),
                action=entry["action"],
                command=list(entry.get("command", [])),
                url=entry.get("url", ""),
                process_names=list(entry.get("process_names", [])),
                response=entry.get("response", ""),
            )
        )
    return apps
