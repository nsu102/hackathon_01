from __future__ import annotations

import base64
import json
import threading
import time
import uuid
from pathlib import Path


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class Events:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.items = []
        self.condition = threading.Condition()

    def emit(self, kind: str, **data):
        with self.condition:
            event = {"seq": len(self.items) + 1, "type": kind, "at": time.time(), "data": data}
            self.items.append(event)
            with (self.folder / "events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            self.condition.notify_all()
            return event

    def read(self, after=0, wait=0):
        with self.condition:
            if len(self.items) <= after and wait:
                self.condition.wait_for(lambda: len(self.items) > after, timeout=min(wait, 20))
            return list(self.items[after:after + 100])


class Exchange:
    """One outstanding native-host request; ids make acknowledgments single-use."""
    def __init__(self, events: Events, budget):
        self.events, self.budget = events, budget
        self.condition = threading.Condition()
        self.pending = None
        self.result = None

    def request(self, operation, arguments, timeout=30, *, reserve=True):
        self.budget.check(reserve=reserve)
        request = {"id": uuid.uuid4().hex, "operation": operation, "arguments": arguments}
        with self.condition:
            if self.pending is not None:
                raise RuntimeError("An exchange already has an outstanding request")
            self.pending, self.result = request, None
            self.events.emit("computer.request", **request)
            end = time.monotonic() + min(timeout, self.budget.working() if reserve else self.budget.remaining())
            try:
                while self.result is None:
                    self.budget.check(reserve=reserve)
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(f"Native host did not answer {operation}")
                    self.condition.wait(min(0.25, remaining))
                result = self.result
                if result.get("error"):
                    raise RuntimeError("Native host failed: " + str(result["error"])[:500])
                return result
            finally:
                self.pending, self.result = None, None
                self.events.emit("computer.request_closed", id=request["id"])

    def answer(self, request_id, result):
        with self.condition:
            if not self.pending or self.pending["id"] != request_id or self.result is not None:
                raise ValueError("Unknown, expired or already answered request")
            if not isinstance(result, dict):
                raise ValueError("result must be an object")
            self.result = result
            self.condition.notify_all()


class Approvals:
    def __init__(self, events, budget):
        self.events, self.budget = events, budget
        self.condition = threading.Condition()
        self.pending = None
        self.decision = None

    def ask(self, preflight, checkpoint=None):
        with self.condition:
            self.budget.check()
            approval_id = uuid.uuid4().hex
            self.pending = {"id": approval_id, **preflight}
            self.decision = None
            self.events.emit("approval.required", **self.pending)
            try:
                while self.decision is None:
                    self.budget.check()
                    if checkpoint:
                        checkpoint()
                    self.condition.wait(0.25)
                if not self.decision:
                    raise PermissionError("User declined the action")
            finally:
                self.pending = None
                self.events.emit("approval.closed", id=approval_id)

    def answer(self, approval_id, approved):
        with self.condition:
            if not self.pending or self.pending["id"] != approval_id or self.decision is not None:
                raise ValueError("Unknown, expired or already answered approval")
            if type(approved) is not bool:
                raise ValueError("approved must be a boolean")
            self.decision = approved
            self.condition.notify_all()


def save_screen(folder: Path, image_url: str) -> tuple[str, str]:
    prefix = "data:image/png;base64,"
    if not isinstance(image_url, str) or not image_url.startswith(prefix) or len(image_url) > 14_000_000:
        raise ValueError("Expected a PNG data URL under 10 MB")
    try:
        raw = base64.b64decode(image_url[len(prefix):], validate=True)
    except Exception as exc:
        raise ValueError("Invalid screenshot encoding") from exc
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Not a PNG screenshot")
    screen_id = uuid.uuid4().hex
    path = folder / "screens" / (screen_id + ".png")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(raw)
    return screen_id, str(path)
