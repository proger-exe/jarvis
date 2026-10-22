from pathlib import Path
import tempfile
import unittest

from jarvis.config import load_apps, load_settings


class ConfigTests(unittest.TestCase):
    def test_load_settings_reads_defaults(self) -> None:
        settings = load_settings(Path("config/settings.toml"))
        self.assertEqual(settings.audio.sample_rate, 16000)
        self.assertEqual(settings.speech.language, "ru")

    def test_load_apps_reads_entries(self) -> None:
        apps = load_apps(Path("config/apps.toml"))
        self.assertGreaterEqual(len(apps), 1)
        self.assertEqual(apps[0].id, "browser")

    def test_partial_settings_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.toml"
            path.write_text("[audio]\nsample_rate = 8000\n", encoding="utf-8")
            settings = load_settings(path)
        self.assertEqual(settings.audio.sample_rate, 8000)
        self.assertEqual(settings.tts.backend, "piper")

    def test_legacy_spd_say_tts_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.toml"
            path.write_text(
                "[tts]\nengine = \"spd-say\"\nvoice = \"ru\"\nrate = -15\n",
                encoding="utf-8",
            )
            settings = load_settings(path)
        self.assertEqual(settings.tts.backend, "spd-say")
        self.assertEqual(settings.tts.spd_say_engine, "spd-say")
        self.assertEqual(settings.tts.spd_say_voice, "ru")
        self.assertEqual(settings.tts.spd_say_rate, -15)


if __name__ == "__main__":
    unittest.main()
