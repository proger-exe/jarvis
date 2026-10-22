import json
import unittest
from unittest.mock import patch

from jarvis.control import send_command


class _FakeSocket:
    def __init__(self, *_args, **_kwargs) -> None:
        self.connected_path = None
        self.sent = b""
        self.closed = False

    def connect(self, path: str) -> None:
        self.connected_path = path

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def recv(self, _size: int) -> bytes:
        return json.dumps({"ok": True, "message": "running"}).encode("utf-8") + b"\n"

    def close(self) -> None:
        self.closed = True


class ControlTests(unittest.TestCase):
    @patch("jarvis.control.socket.socket", return_value=_FakeSocket())
    def test_send_command(self, _mock_socket) -> None:
        response = send_command("/tmp/jarvis.sock", "status")
        self.assertTrue(response.ok)
        self.assertEqual(response.message, "running")

    def test_missing_socket(self) -> None:
        response = send_command("/tmp/definitely-missing-jarvis.sock", "status")
        self.assertFalse(response.ok)


if __name__ == "__main__":
    unittest.main()
