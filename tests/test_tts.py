import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.config import TtsConfig
from jarvis.tts import PiperTtsEngine, SpdSayTtsEngine, choose_player, create_tts_engine, resolve_piper_paths


class TtsTests(unittest.TestCase):
    def test_resolve_piper_paths(self) -> None:
        config = TtsConfig(voice_model="ru_RU-irina-medium", voice_dir="/tmp/voices")
        model_path, config_path = resolve_piper_paths(config)
        self.assertEqual(str(model_path), "/tmp/voices/ru_RU-irina-medium.onnx")
        self.assertEqual(str(config_path), "/tmp/voices/ru_RU-irina-medium.onnx.json")

    @patch("jarvis.tts.which", side_effect=lambda name: "/usr/bin/" + name if name == "ffplay" else None)
    def test_choose_player_fallback(self, _mock_which) -> None:
        self.assertEqual(choose_player("paplay"), "ffplay")

    def test_create_tts_engine_defaults_to_piper(self) -> None:
        engine = create_tts_engine(TtsConfig())
        self.assertIsInstance(engine, PiperTtsEngine)

    def test_create_tts_engine_supports_spd_say(self) -> None:
        engine = create_tts_engine(TtsConfig(backend="spd-say"))
        self.assertIsInstance(engine, SpdSayTtsEngine)

    def test_piper_doctor_lines_report_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PiperTtsEngine(TtsConfig(voice_dir=tmpdir))
            lines = engine.doctor_lines()
        self.assertTrue(any("piper model exists: False" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
