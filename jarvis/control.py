from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import socket


@dataclass(slots=True)
class ControlResponse:
    ok: bool
    message: str
    state: dict[str, object] | None = None


def send_command(socket_path: str, command: str) -> ControlResponse:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(socket_path)
        payload = json.dumps({"command": command}).encode("utf-8") + b"\n"
        client.sendall(payload)
        data = b""
        while not data.endswith(b"\n"):
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk
    except FileNotFoundError:
        return ControlResponse(ok=False, message=f"Socket not found: {socket_path}")
    except OSError as exc:
        return ControlResponse(ok=False, message=str(exc))
    finally:
        client.close()
    if not data:
        return ControlResponse(ok=False, message="No response from daemon")
    decoded = json.loads(data.decode("utf-8"))
    return ControlResponse(ok=decoded["ok"], message=decoded["message"], state=decoded.get("state"))


def ensure_socket_parent(socket_path: str) -> None:
    Path(socket_path).parent.mkdir(parents=True, exist_ok=True)
