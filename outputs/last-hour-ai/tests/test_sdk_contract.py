"""Offline replay through the real OpenAI SDK. Does not make API requests."""
import asyncio
import base64
from pathlib import Path
import tempfile
import unittest

from last_hour.cli import demo_task
from last_hour.driver import ComputerDriver
from last_hour.engine import Session
from last_hour.models import Task

try:
    from openai import AsyncComputerToolset
    from openai.types.responses.response_computer_tool_call import ResponseComputerToolCall
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


@unittest.skipUnless(HAS_SDK, "Install .[live] to run the real SDK replay tests")
class SDKContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_dispatches_to_bridge_and_captures_screen(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Session(Task.parse(demo_task()), Path(tmp))
            operations = []
            class Host:
                def request(self, operation, arguments, **kwargs):
                    operations.append(operation)
                    scope = {"app": "assignment-demo", "url": None}
                    if operation == "screenshot":
                        return {"scope": scope, "width": 1, "height": 1,
                                "image_url": "data:image/png;base64," + base64.b64encode(
                                    b"\x89PNG\r\n\x1a\n" + b"test-only-placeholder").decode()}
                    if operation == "preflight":
                        return {"allowed": True, "effect": "edit", "token": "test-token",
                                "state_id": "test-state", "summary": "Test typing", "scope": scope}
                    return {"executed": True, "scope": scope}
            driver = ComputerDriver(session, Host(), 0)
            toolset = AsyncComputerToolset(driver)
            call = ResponseComputerToolCall(
                id="cu_test", call_id="call_test", type="computer_call", status="completed",
                pending_safety_checks=[], action={"type": "type", "text": "Test answer"},
            )
            try:
                output = await toolset.execute(call, before_action=driver.allowed)
                self.assertEqual(output["call_id"], "call_test")
                self.assertEqual(operations, ["preflight", "execute", "screenshot"])
                self.assertEqual(len(list((session.folder / "screens").glob("*.png"))), 1)
            finally:
                toolset.close()

    async def test_real_sdk_does_not_auto_approve_pending_safety_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Session(Task.parse(demo_task()), Path(tmp))
            class Host:
                def request(self, *args, **kwargs):
                    raise AssertionError("Host must not be called")
            toolset = AsyncComputerToolset(ComputerDriver(session, Host(), 0))
            call = ResponseComputerToolCall(
                id="cu_safety", call_id="call_safety", type="computer_call", status="completed",
                pending_safety_checks=[{"id": "check_test", "code": "test", "message": "Confirm"}],
                action={"type": "screenshot"},
            )
            try:
                with self.assertRaises(Exception) as caught:
                    await toolset.execute(call)
                self.assertIn("explicit approval", str(caught.exception))
            finally:
                toolset.close()
