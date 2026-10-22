from __future__ import annotations

from pathlib import Path
import json


class SpeechRecognizer:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._model = None

    def ensure_ready(self) -> None:
        if self._model is not None:
            return
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Vosk model not found: {self.model_path}")
        try:
            from vosk import Model
        except ImportError as exc:
            raise RuntimeError("Package 'vosk' is not installed.") from exc
        self._model = Model(self.model_path)

    def transcribe(self, pcm_bytes: bytes, sample_rate: int) -> str:
        self.ensure_ready()
        try:
            from vosk import KaldiRecognizer
        except ImportError as exc:
            raise RuntimeError("Package 'vosk' is not installed.") from exc
        recognizer = KaldiRecognizer(self._model, sample_rate)
        chunk_size = 4000
        for index in range(0, len(pcm_bytes), chunk_size):
            recognizer.AcceptWaveform(pcm_bytes[index : index + chunk_size])
        final_result = json.loads(recognizer.FinalResult())
        return str(final_result.get("text", "")).strip()
