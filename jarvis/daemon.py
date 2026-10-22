from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import which
from socketserver import StreamRequestHandler, UnixStreamServer
from threading import Event, Lock, Thread
import json
import logging
import os
import socket
import subprocess
import time

from jarvis.audio import list_sources, resolve_source, start_ffmpeg_capture
from jarvis.config import AppSpec, Settings, load_apps, load_settings
from jarvis.control import ensure_socket_parent
from jarvis.intents import focus_window, launch_command, match_intent, open_url
from jarvis.stt import SpeechRecognizer
from jarvis.tray import spawn_tray
from jarvis.tts import create_tts_engine


LOGGER = logging.getLogger("jarvis")


def ensure_runtime_dir() -> Path:
    path = Path("runtime")
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging() -> Path:
    runtime_dir = ensure_runtime_dir()
    log_path = runtime_dir / "jarvis.log"
    if not LOGGER.handlers:
        LOGGER.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
        LOGGER.addHandler(stream_handler)
    return log_path


def notify(message: str) -> None:
    if which("notify-send") is None or not os.environ.get("DISPLAY"):
        return
    subprocess.Popen(
        ["notify-send", "Jarvis", message],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def load_vad(level: int):
    try:
        import webrtcvad
    except ImportError as exc:
        raise RuntimeError("Package 'webrtcvad' is not installed.") from exc
    return webrtcvad.Vad(level)


def chunk_bytes(data: bytes, size: int) -> list[bytes]:
    return [data[index : index + size] for index in range(0, len(data), size) if len(data[index : index + size]) == size]


@dataclass(slots=True)
class DispatchResult:
    matched: bool
    message: str = ""


class ControlRequestHandler(StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send({"ok": False, "message": "Invalid JSON"})
            return
        daemon = self.server.daemon_ref
        command = payload.get("command", "")
        response = daemon.handle_control_command(command)
        self._send(response)

    def _send(self, payload: dict[str, object]) -> None:
        self.wfile.write(json.dumps(payload).encode("utf-8") + b"\n")


class ControlServer(UnixStreamServer):
    allow_reuse_address = True

    def __init__(self, socket_path: str, daemon_ref: "JarvisDaemon") -> None:
        if Path(socket_path).exists():
            Path(socket_path).unlink()
        ensure_socket_parent(socket_path)
        super().__init__(socket_path, ControlRequestHandler)
        self.daemon_ref = daemon_ref


class JarvisDaemon:
    def __init__(self, settings_path: str, apps_path: str) -> None:
        self.settings_path = settings_path
        self.apps_path = apps_path
        self.log_path = configure_logging()
        self._lock = Lock()
        self._stop_event = Event()
        self._paused_event = Event()
        self._speaking_event = Event()
        self._tray_process = None
        self._capture_process = None
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self.settings: Settings = load_settings(self.settings_path)
            self.apps: list[AppSpec] = load_apps(self.apps_path)
            self.source_name = resolve_source(self.settings.audio)
            self.recognizer = SpeechRecognizer(self.settings.speech.model_path)
            self.tts_engine = create_tts_engine(self.settings.tts)

    @property
    def paused(self) -> bool:
        return self._paused_event.is_set()

    @property
    def speaking(self) -> bool:
        return self._speaking_event.is_set()

    def run_forever(self) -> int:
        if not self.source_name:
            raise RuntimeError("No audio input source found. Run 'python -m jarvis list-devices'.")
        control_thread = self._start_control_server()
        self._spawn_tray_if_enabled()
        if self.settings.ui.notify_on_error:
            notify("Ассистент запущен")
        LOGGER.info("Jarvis started with source=%s", self.source_name)
        try:
            self._audio_loop()
        finally:
            self._stop_event.set()
            self._shutdown_capture()
            self._shutdown_tray()
            self._shutdown_control_server()
            control_thread.join(timeout=2)
            if self.settings.ui.notify_on_error:
                notify("Ассистент остановлен")
        return 0

    def _spawn_tray_if_enabled(self) -> None:
        if not self.settings.ui.tray_enabled:
            return
        self._tray_process = spawn_tray(
            socket_path=self.settings.control.socket_path,
            settings_path=str(Path(self.settings_path).resolve()),
            apps_path=str(Path(self.apps_path).resolve()),
            log_path=str(self.log_path.resolve()),
        )

    def _start_control_server(self) -> Thread:
        self.control_server = ControlServer(self.settings.control.socket_path, self)
        thread = Thread(target=self.control_server.serve_forever, name="jarvis-control", daemon=True)
        thread.start()
        return thread

    def _shutdown_control_server(self) -> None:
        if hasattr(self, "control_server"):
            self.control_server.shutdown()
            self.control_server.server_close()
            socket_path = Path(self.settings.control.socket_path)
            if socket_path.exists():
                socket_path.unlink()

    def _shutdown_capture(self) -> None:
        if self._capture_process is not None and self._capture_process.poll() is None:
            self._capture_process.terminate()
            try:
                self._capture_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._capture_process.kill()

    def _shutdown_tray(self) -> None:
        if self._tray_process is not None and self._tray_process.poll() is None:
            self._tray_process.terminate()

    def _audio_loop(self) -> None:
        vad = load_vad(self.settings.audio.vad_aggressiveness)
        self._capture_process = start_ffmpeg_capture(self.settings.audio, self.source_name)
        if self._capture_process.stdout is None:
            raise RuntimeError("ffmpeg capture did not expose stdout")
        frame_size = self.settings.audio.frame_size_bytes
        silence_frames_needed = max(1, self.settings.audio.silence_ms // self.settings.audio.chunk_duration_ms)
        min_speech_frames = max(1, self.settings.audio.min_speech_ms // self.settings.audio.chunk_duration_ms)
        speech_frames: list[bytes] = []
        silence_frames = 0
        while not self._stop_event.is_set():
            frame = self._capture_process.stdout.read(frame_size)
            if not frame:
                if self._capture_process.poll() is not None:
                    raise RuntimeError("ffmpeg capture stopped unexpectedly")
                time.sleep(0.03)
                continue
            if self.paused or self.speaking:
                speech_frames.clear()
                silence_frames = 0
                continue
            is_speech = vad.is_speech(frame, self.settings.audio.sample_rate)
            if is_speech:
                speech_frames.append(frame)
                silence_frames = 0
                continue
            if speech_frames:
                silence_frames += 1
                speech_frames.append(frame)
                if silence_frames < silence_frames_needed:
                    continue
                if len(speech_frames) >= min_speech_frames:
                    audio_bytes = b"".join(speech_frames)
                    self._handle_utterance(audio_bytes)
                speech_frames.clear()
                silence_frames = 0

    def _handle_utterance(self, audio_bytes: bytes) -> None:
        try:
            transcript = self.recognizer.transcribe(audio_bytes, self.settings.audio.sample_rate)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Speech recognition failed: %s", exc)
            if self.settings.ui.notify_on_error:
                notify(f"Ошибка распознавания: {exc}")
            return
        if not transcript:
            return
        LOGGER.info("Transcript: %s", transcript)
        result = self._dispatch_transcript(transcript)
        if result.message:
            self.speak(result.message)

    def _dispatch_transcript(self, transcript: str) -> DispatchResult:
        match = match_intent(transcript, self.apps)
        if match is None:
            LOGGER.info("No intent matched")
            return DispatchResult(matched=False)
        app = match.app
        LOGGER.info("Matched intent '%s' with action '%s'", app.id, app.action)
        if app.action == "speak":
            return DispatchResult(matched=True, message=app.response)
        if app.action == "focus_or_launch":
            focused = focus_window(app.process_names)
            if not focused:
                launch_command(app.command)
            return DispatchResult(matched=True, message=app.response)
        if app.action == "launch":
            launch_command(app.command)
            return DispatchResult(matched=True, message=app.response)
        if app.action == "open_url":
            open_url(app.url)
            return DispatchResult(matched=True, message=app.response)
        LOGGER.warning("Unknown action '%s' in apps config", app.action)
        return DispatchResult(matched=False)

    def speak(self, message: str) -> None:
        if not message:
            return
        self._speaking_event.set()
        try:
            self.tts_engine.speak(message)
        finally:
            time.sleep(0.5)
            self._speaking_event.clear()

    def handle_control_command(self, command: str) -> dict[str, object]:
        if command == "status":
            return {
                "ok": True,
                "message": "running",
                "state": {
                    "paused": self.paused,
                    "speaking": self.speaking,
                    "source": self.source_name,
                    "apps": [app.id for app in self.apps],
                },
            }
        if command == "pause":
            self._paused_event.set()
            return {"ok": True, "message": "paused"}
        if command == "resume":
            self._paused_event.clear()
            return {"ok": True, "message": "resumed"}
        if command == "reload":
            self.reload()
            return {"ok": True, "message": "reloaded"}
        if command == "stop":
            self._stop_event.set()
            dummy = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                dummy.connect(self.settings.control.socket_path)
            except OSError:
                pass
            finally:
                dummy.close()
            return {"ok": True, "message": "stopping"}
        return {"ok": False, "message": f"Unknown command: {command}"}


def run_doctor(settings_path: str, apps_path: str) -> int:
    settings = load_settings(settings_path)
    apps = load_apps(apps_path)
    sources = list_sources()
    tts_engine = create_tts_engine(settings.tts)
    requirements = {
        "ffmpeg": which("ffmpeg") is not None,
        "pactl": which("pactl") is not None,
        "wmctrl": which("wmctrl") is not None,
        "notify-send": which("notify-send") is not None,
        "yad": which("yad") is not None,
    }
    print("Jarvis doctor")
    print(f"settings: {Path(settings_path).resolve()}")
    print(f"apps: {Path(apps_path).resolve()}")
    print(f"vosk model exists: {Path(settings.speech.model_path).exists()}")
    print(f"configured source: {settings.audio.source or '<auto>'}")
    print(f"selected source: {resolve_source(settings.audio) or '<none>'}")
    print(f"known devices: {len(sources)}")
    print(f"configured apps: {len(apps)}")
    for name, ok in requirements.items():
        print(f"{name}: {'ok' if ok else 'missing'}")
    for line in tts_engine.doctor_lines():
        print(line)
    try:
        load_vad(settings.audio.vad_aggressiveness)
        print("webrtcvad: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"webrtcvad: {exc}")
    try:
        SpeechRecognizer(settings.speech.model_path).ensure_ready()
        print("vosk: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"vosk: {exc}")
    try:
        if hasattr(tts_engine, "ensure_ready"):
            tts_engine.ensure_ready()
        print("tts: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"tts: {exc}")
    return 0
