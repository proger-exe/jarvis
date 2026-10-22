from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import which
from subprocess import DEVNULL, PIPE
import subprocess

from jarvis.config import TtsConfig


@dataclass(slots=True)
class AudioBuffer:
    pcm_bytes: bytes
    sample_rate: int
    channels: int = 1
    sample_width: int = 2


def resolve_piper_paths(config: TtsConfig) -> tuple[Path, Path]:
    voice_dir = Path(config.voice_dir)
    model_path = voice_dir / f"{config.voice_model}.onnx"
    config_path = Path(f"{model_path}.json")
    return model_path, config_path


def choose_player(preferred: str) -> str:
    for candidate in (preferred, "paplay", "ffplay", "aplay"):
        if candidate and which(candidate) is not None:
            return candidate
    raise RuntimeError("No audio player found. Install paplay, ffplay, or aplay.")


class BaseTtsEngine:
    def speak(self, message: str) -> None:
        raise NotImplementedError

    def doctor_lines(self) -> list[str]:
        raise NotImplementedError


class PiperTtsEngine(BaseTtsEngine):
    def __init__(self, config: TtsConfig) -> None:
        self.config = config
        self._voice = None
        self.player = choose_player(config.player)

    def ensure_ready(self) -> None:
        if self._voice is not None:
            return
        model_path, config_path = resolve_piper_paths(self.config)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper voice model not found: {model_path}. "
                f"Download with: .venv/bin/python -m piper.download_voices --data-dir {self.config.voice_dir} {self.config.voice_model}"
            )
        if not config_path.exists():
            raise FileNotFoundError(
                f"Piper voice config not found: {config_path}. "
                f"Download with: .venv/bin/python -m piper.download_voices --data-dir {self.config.voice_dir} {self.config.voice_model}"
            )
        try:
            from piper.voice import PiperVoice
        except ImportError as exc:
            raise RuntimeError("Package 'piper-tts' is not installed.") from exc
        self._voice = PiperVoice.load(
            model_path=model_path,
            config_path=config_path,
            use_cuda=self.config.use_cuda,
            download_dir=self.config.voice_dir,
        )

    def _synthesize(self, message: str) -> AudioBuffer:
        self.ensure_ready()
        try:
            from piper.config import SynthesisConfig
        except ImportError as exc:
            raise RuntimeError("Package 'piper-tts' is not installed.") from exc
        syn_config = SynthesisConfig(
            length_scale=self.config.length_scale,
            noise_scale=self.config.noise_scale,
            noise_w_scale=self.config.noise_w_scale,
            normalize_audio=self.config.normalize_audio,
            volume=self.config.volume,
        )
        pcm_parts: list[bytes] = []
        sample_rate = None
        for chunk in self._voice.synthesize(message, syn_config=syn_config):
            sample_rate = chunk.sample_rate
            pcm_parts.append(chunk.audio_int16_bytes)
        if sample_rate is None:
            raise RuntimeError("Piper did not return audio for the given text.")
        return AudioBuffer(pcm_bytes=b"".join(pcm_parts), sample_rate=sample_rate)

    def _play(self, audio: AudioBuffer) -> None:
        if self.player == "paplay":
            command = [
                "paplay",
                "--raw",
                f"--rate={audio.sample_rate}",
                f"--channels={audio.channels}",
                "--format=s16le",
            ]
        elif self.player == "ffplay":
            command = [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "error",
                "-f",
                "s16le",
                "-ar",
                str(audio.sample_rate),
                "-ac",
                str(audio.channels),
                "pipe:0",
            ]
        else:
            command = [
                "aplay",
                "-q",
                "-t",
                "raw",
                "-f",
                "S16_LE",
                "-r",
                str(audio.sample_rate),
                "-c",
                str(audio.channels),
            ]
        player = subprocess.Popen(command, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)
        try:
            player.communicate(audio.pcm_bytes)
        finally:
            if player.poll() is None:
                player.kill()
        if player.returncode not in (0, None):
            raise RuntimeError(f"Audio playback failed via {self.player}.")

    def speak(self, message: str) -> None:
        audio = self._synthesize(message)
        self._play(audio)

    def doctor_lines(self) -> list[str]:
        model_path, config_path = resolve_piper_paths(self.config)
        return [
            f"tts backend: piper",
            f"tts voice model: {self.config.voice_model}",
            f"tts player: {self.player}",
            f"piper import: {'ok' if _can_import_piper() else 'missing'}",
            f"piper model exists: {model_path.exists()}",
            f"piper config exists: {config_path.exists()}",
            f"piper download command: .venv/bin/python -m piper.download_voices --data-dir {self.config.voice_dir} {self.config.voice_model}",
        ]


class SpdSayTtsEngine(BaseTtsEngine):
    def __init__(self, config: TtsConfig) -> None:
        self.config = config

    def ensure_ready(self) -> None:
        if which(self.config.spd_say_engine) is None:
            raise RuntimeError(f"'{self.config.spd_say_engine}' is not installed.")

    def speak(self, message: str) -> None:
        self.ensure_ready()
        subprocess.run(
            [
                self.config.spd_say_engine,
                "-l",
                self.config.spd_say_voice,
                "-r",
                str(self.config.spd_say_rate),
                message,
            ],
            check=False,
            stdout=DEVNULL,
            stderr=DEVNULL,
        )

    def doctor_lines(self) -> list[str]:
        return [
            "tts backend: spd-say",
            f"spd-say binary: {'ok' if which(self.config.spd_say_engine) else 'missing'}",
            f"spd-say voice: {self.config.spd_say_voice}",
            f"spd-say rate: {self.config.spd_say_rate}",
        ]


def _can_import_piper() -> bool:
    try:
        import piper.voice  # noqa: F401
    except ImportError:
        return False
    return True


def create_tts_engine(config: TtsConfig) -> BaseTtsEngine:
    if config.backend == "piper":
        return PiperTtsEngine(config)
    if config.backend == "spd-say":
        return SpdSayTtsEngine(config)
    raise RuntimeError(f"Unsupported TTS backend: {config.backend}")
