"""OpenRouter protocol tests with fake responses; no external inference requests."""
from contextlib import asynccontextmanager
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from last_hour.cli import demo_task
from last_hour.config import DEFAULT_MODEL, ModelSettings, load_env
from last_hour.driver import ComputerDriver
from last_hour.engine import Session
from last_hour.models import Task
from last_hour.openrouter import (
    OpenRouterClient, ProviderError, assistant_message, execute_openrouter,
    limit_images, validate_action,
)
from last_hour.policy import RULES, assignment_plan, ModelPolicy, task_input


PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQkAAAAASUVORK5CYII="


def settings():
    return ModelSettings("openrouter", "test-secret-not-real", DEFAULT_MODEL, DEFAULT_MODEL,
                         "https://openrouter.ai/api/v1")


def completion(content=None, tool=None, arguments=None, call_id="call_1", finish_reason=None):
    message = {"role": "assistant", "content": content}
    if tool:
        message["tool_calls"] = [{"id": call_id, "type": "function", "function": {
            "name": tool, "arguments": json.dumps(arguments),
        }}]
    return {"choices": [{"finish_reason": finish_reason or ("tool_calls" if tool else "stop"), "message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.00001}}


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def complete(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        if not self.responses:
            raise AssertionError("Unexpected extra model request")
        return self.responses.pop(0)


class FakeHost:
    def __init__(self):
        self.calls = []
        self.verifies = True
        self.pending = None

    def request(self, operation, arguments, **kwargs):
        self.calls.append((operation, arguments))
        scope = {"app": "assignment-demo", "url": None}
        if operation == "screenshot":
            return {"scope": scope, "width": 1024, "height": 768, "image_url": PNG}
        if operation == "preflight":
            return {"allowed": True, "effect": "edit", "scope": scope, "state_id": "current-state",
                    "token": "one-use-target-token", "summary": "Edit the test answer"}
        if operation == "execute":
            return {"executed": True, "scope": scope}
        if operation == "verify":
            return {"checks": [{"id": c["id"], "passed": self.verifies, "evidence": "Independent fixture observation"}
                               for c in arguments["criteria"]]}
        raise AssertionError("Unknown host request")


class ConfigTests(unittest.TestCase):
    def test_dotenv_is_loaded_without_executing_or_overwriting_exports(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"EXISTING": "exported"}, clear=True):
            path = Path(tmp) / ".env"
            path.write_text('export EXISTING=file\nOPENROUTER_API_KEY="key#fragment" # comment\n'
                            'EMPTY=\nLITERAL="$(a_command) $HOME"\n')
            load_env(path)
            import os
            self.assertEqual(os.environ["EXISTING"], "exported")
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "key#fragment")
            self.assertEqual(os.environ["EMPTY"], "")
            self.assertEqual(os.environ["LITERAL"], "$(a_command) $HOME")

    def test_bad_dotenv_is_atomic_and_does_not_expose_secret(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {}, clear=True):
            path = Path(tmp) / ".env"
            path.write_text('FIRST=value\nSECRET="private-unclosed-value\n')
            with self.assertRaises(ValueError) as caught:
                load_env(path)
            import os
            self.assertNotIn("FIRST", os.environ)
            self.assertNotIn("private-unclosed", str(caught.exception))

    def test_default_and_role_models_and_secret_redaction(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-never-show", "OPENROUTER_POLICY_MODEL": "anthropic/claude-haiku-5.5"}, clear=True):
            config = ModelSettings.read()
            self.assertEqual(config.provider, "openrouter")
            self.assertEqual(config.computer_model, DEFAULT_MODEL)
            self.assertEqual(config.policy_model, "anthropic/claude-haiku-5.5")
            self.assertNotIn("test-key-never-show", repr(config))
            self.assertNotIn("test-key-never-show", json.dumps(config.public()))
            config.require_key()

    def test_missing_key_and_invalid_base_url_are_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
                ModelSettings.read().require_key()
        with patch.dict("os.environ", {"OPENROUTER_BASE_URL": "http://public.example/api"}, clear=True):
            with self.assertRaises(ValueError):
                ModelSettings.read()


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Session(Task.parse(demo_task()), Path(self.tmp.name), settings=settings())
        self.session.plan = assignment_plan()
        self.host = FakeHost()
        self.driver = ComputerDriver(self.session, self.host, 0)

    def tearDown(self):
        self.tmp.cleanup()

    async def test_transport_sends_tools_and_reasoning_to_openrouter_without_an_sdk(self):
        captured = []
        raw = json.dumps(completion('{"ok":true}')).encode()
        class Opener:
            def open(self, request, timeout):
                captured.append((request, timeout))
                return io.BytesIO(raw)
        with patch("last_hour.openrouter.build_opener", return_value=Opener()):
            result = await OpenRouterClient(settings()).complete(
                model=DEFAULT_MODEL, messages=[{"role": "user", "content": "test"}],
                tools=[{"type": "function", "function": {"name": "test"}}])
        request, timeout = captured[0]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], DEFAULT_MODEL)
        self.assertNotIn("parallel_tool_calls", payload)
        self.assertTrue(payload["provider"]["require_parameters"])
        self.assertEqual(payload["reasoning"], {"effort": "low", "exclude": True})
        self.assertEqual(timeout, 30)
        self.assertIn("choices", result)

    async def test_http_errors_do_not_echo_upstream_secrets(self):
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 401, "upstream echoed test-secret-not-real", {}, None)
        with patch("last_hour.openrouter.build_opener", return_value=Opener()):
            with self.assertRaises(ProviderError) as caught:
                await OpenRouterClient(settings()).complete(model=DEFAULT_MODEL, messages=[])
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("test-secret", str(caught.exception))

    async def test_planner_uses_router_schema_and_canonical_messages(self):
        self.session.planner_input = task_input(self.session.task, 3600, ["파일을 먼저 확인"])
        client = FakeClient([completion(json.dumps(assignment_plan()))])
        plan = await ModelPolicy().plan(self.session, client)
        self.assertEqual(plan, assignment_plan())
        self.assertEqual(client.requests[0]["response_format"]["type"], "json_schema")
        self.assertIn("파일을 먼저 확인", client.requests[0]["messages"][-1]["content"])

    async def test_screenshot_action_tool_result_and_reobservation_loop(self):
        first = completion(tool="computer_action", arguments={"action": {"type": "type", "text": "My draft"}})
        first["choices"][0]["message"]["reasoning_details"] = [{"type": "reasoning.encrypted", "data": "signature"}]
        client = FakeClient([
            first,
            completion(tool="finish", arguments={"status": "ready_for_verification", "message": "초안을 확인해주세요"}, call_id="call_2"),
        ])
        result = await execute_openrouter(self.session, self.driver, client, settings(), RULES)
        self.assertEqual(result["status"], "ready_for_verification")
        self.assertEqual([name for name, _ in self.host.calls], ["screenshot", "preflight", "execute", "screenshot"])
        self.assertTrue(any(p.get("type") == "image_url" for p in client.requests[0]["messages"][-1]["content"]))
        second_messages = client.requests[1]["messages"]
        self.assertTrue(any(m.get("tool_call_id") == "call_1" for m in second_messages))
        self.assertTrue(any(m.get("reasoning_details") for m in second_messages))
        self.assertEqual(self.session.action_count, 1)
        self.assertNotEqual(self.session.status, "completed")  # Final model words cannot self-certify.

    async def test_parallel_actions_are_rejected_before_any_effect(self):
        response = completion(tool="computer_action", arguments={"action": {"type": "type", "text": "draft"}})
        response["choices"][0]["message"]["tool_calls"] *= 2
        with self.assertRaises(ProviderError):
            await execute_openrouter(self.session, self.driver, FakeClient([response]), settings(), RULES)
        self.assertEqual([name for name, _ in self.host.calls], ["screenshot"])

    async def test_truncation_never_executes_partial_tool_calls(self):
        response = completion(tool="computer_action", arguments={"action": {"type": "type", "text": "draft"}}, finish_reason="length")
        with self.assertRaises(ProviderError):
            await execute_openrouter(self.session, self.driver, FakeClient([response]), settings(), RULES)
        self.assertEqual([name for name, _ in self.host.calls], ["screenshot"])

    async def test_missing_input_finishes_with_a_question_without_actions(self):
        client = FakeClient([completion(tool="finish", arguments={"status": "needs_input", "message": "어느 파일인가요?"})])
        result = await execute_openrouter(self.session, self.driver, client, settings(), RULES)
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(self.session.action_count, 0)

    async def test_engine_independent_verification_rejects_false_model_success(self):
        self.session.task.mode = "live"
        self.session.exchange = self.host
        self.host.verifies = False
        client = FakeClient([completion(json.dumps(assignment_plan())),
            completion(tool="finish", arguments={"status": "ready_for_verification", "message": "완료했습니다"})])
        @asynccontextmanager
        async def fake_model_client(config):
            yield client
        with patch("last_hour.engine.model_client", fake_model_client):
            await self.session.run()
        self.assertEqual(self.session.status, "handoff")
        self.assertIsNone(self.session.verification)

    async def test_engine_marks_complete_only_after_host_checks_pass(self):
        self.session.task.mode = "live"
        self.session.exchange = self.host
        client = FakeClient([completion(json.dumps(assignment_plan())),
            completion(tool="finish", arguments={"status": "ready_for_verification", "message": "검증해주세요"})])
        @asynccontextmanager
        async def fake_model_client(config):
            yield client
        with patch("last_hour.engine.model_client", fake_model_client):
            await self.session.run()
        self.assertEqual(self.session.status, "completed")
        self.assertTrue(all(c["passed"] for c in self.session.verification["checks"]))

    def test_action_schema_blocks_malformed_coordinates_and_unknown_fields(self):
        cases = [{"type": "click", "x": True, "y": 1, "button": "left"},
                 {"type": "type", "text": "test", "shell": "injected"},
                 {"type": "drag", "path": []}, {"type": "keypress", "keys": []}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ProviderError):
                validate_action(value)

    def test_only_recent_images_are_retained_without_mutating_history(self):
        messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": PNG}}]} for _ in range(5)]
        trimmed = limit_images(messages, keep=3)
        self.assertEqual(sum(p["type"] == "image_url" for m in trimmed for p in m["content"]), 3)
        self.assertEqual(sum(p["type"] == "image_url" for m in messages for p in m["content"]), 5)
