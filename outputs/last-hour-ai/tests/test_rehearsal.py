"""Opt-in real-browser integration tests; never contact a real school portal."""
import importlib.util
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from last_hour.cli import demo_task
from last_hour.engine import Service, TERMINAL
from last_hour.engine import Session
from last_hour.config import ModelSettings, DEFAULT_MODEL
from last_hour.models import Task
from last_hour.policy import assignment_plan


@unittest.skipUnless(os.getenv("LAST_HOUR_BROWSER_TESTS") == "1" and importlib.util.find_spec("playwright"),
                     "Set LAST_HOUR_BROWSER_TESTS=1 and install .[demo] for real browser tests")
class BrowserIntegrationTests(unittest.TestCase):
    def run_case(self, approve):
        with tempfile.TemporaryDirectory() as directory:
            session = Service(directory).create(demo_task())
            cursor, deadline = 0, time.monotonic() + 30
            while session.status not in TERMINAL and time.monotonic() < deadline:
                for event in session.events.read(cursor, wait=0.1):
                    cursor = event["seq"]
                    if event["type"] == "approval.required":
                        session.approvals.answer(event["data"]["id"], approve)
            if session.status not in TERMINAL:
                session.cancel()
            session.worker.join(6)
            self.assertEqual(session.status, "completed" if approve else "handoff")
            self.assertEqual((session.folder / "draft.txt").read_text(), demo_task()["context"])
            submit_actions = [e for e in session.events.items if e["type"] == "computer.action" and e["data"]["effect"] == "submit"]
            self.assertEqual(len(submit_actions), 1 if approve else 0)
            if approve:
                self.assertTrue(all(c["passed"] for c in session.verification["checks"]))
                self.assertEqual(len(list((session.folder / "screens").glob("*.png"))), 2)
            else:
                self.assertIsNone(session.verification)

    def test_approved_submission_has_real_receipt_and_matching_saved_draft(self):
        self.run_case(True)

    def test_declined_submission_preserves_draft_without_submitting(self):
        self.run_case(False)


@unittest.skipUnless(os.getenv("LAST_HOUR_BROWSER_TESTS") == "1" and importlib.util.find_spec("playwright"),
                     "Set LAST_HOUR_BROWSER_TESTS=1 for sandbox integration")
class OverlaySandboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_router_tool_loop_uses_real_browser_and_approval_without_external_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Task.parse({**demo_task(), "mode": "live", "environment": "sandbox"})
            config = ModelSettings("openrouter", "offline-key-not-sent", DEFAULT_MODEL, DEFAULT_MODEL,
                                   "https://openrouter.ai/api/v1")
            session = Session(task, Path(directory), settings=config)
            class ScriptedModel:
                turn = 0
                async def complete(self, **kwargs):
                    if kwargs.get("response_format"):
                        return {"choices": [{"finish_reason": "stop", "message": {
                            "role": "assistant", "content": json.dumps(assignment_plan())}}]}
                    index = self.turn
                    self.turn += 1
                    if index == 4:
                        name, arguments = "finish", {"status": "ready_for_verification", "message": "접수증을 확인해주세요"}
                    else:
                        if index == 1:
                            value = {"type": "type", "text": task.context}
                        else:
                            control = "answer" if index == 0 else "save" if index == 2 else "submit"
                            box = session.portal_host.controls[control]
                            value = {"type": "click", "button": "left", "x": int(box["x"] + box["width"] / 2),
                                     "y": int(box["y"] + box["height"] / 2)}
                        name, arguments = "computer_action", {"action": value}
                    return {"choices": [{"finish_reason": "tool_calls", "message": {
                        "role": "assistant", "content": None, "tool_calls": [{"id": f"call_{index}", "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]}
            @asynccontextmanager
            async def client(_settings):
                yield ScriptedModel()
            async def approve():
                while session.status not in TERMINAL:
                    if session.approvals.pending:
                        session.approvals.answer(session.approvals.pending["id"], True)
                        return
                    await asyncio.sleep(0.01)
            with patch("last_hour.engine.model_client", client):
                approval = asyncio.create_task(approve())
                await asyncio.wait_for(session.run(), 20)
                await asyncio.wait_for(approval, 1)
            self.assertEqual(session.status, "completed")
            self.assertFalse(session.portal_host.thread.is_alive())
            self.assertEqual(session.action_count, 4)
            self.assertTrue(all(check["passed"] for check in session.verification["checks"]))
