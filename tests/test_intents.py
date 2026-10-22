import unittest
from unittest.mock import patch

from jarvis.config import AppSpec
from jarvis.intents import focus_window, match_intent, normalize_text


class IntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.apps = [
            AppSpec(
                id="browser",
                phrases=["открой браузер"],
                action="focus_or_launch",
                command=["firefox"],
                process_names=["firefox"],
                response="Открываю браузер.",
            )
        ]

    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("  Открой   браузер!! "), "открой браузер")

    def test_match_intent(self) -> None:
        match = match_intent("Открой браузер", self.apps)
        self.assertIsNotNone(match)
        self.assertEqual(match.app.id, "browser")

    @patch("jarvis.intents.which", return_value="/usr/bin/wmctrl")
    @patch("jarvis.intents.subprocess.run")
    def test_focus_window(self, mock_run, _mock_which) -> None:
        mock_run.side_effect = [
            type("Completed", (), {"returncode": 0, "stdout": "0x01  0 firefox.Firefox host Firefox\n"})(),
            type("Completed", (), {"returncode": 0})(),
        ]
        self.assertTrue(focus_window(["firefox"]))


if __name__ == "__main__":
    unittest.main()
