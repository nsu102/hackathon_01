import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

from last_hour.cli import demo_task
from last_hour.driver import ComputerDriver, ReplanRequested, action
from last_hour.engine import Session
from last_hour.models import Budget, Stopped, Task, check_scope, validate_plan, validate_verification
from last_hour.policy import LearningStore, assignment_plan, task_input
from last_hour.storage import Approvals, Events, Exchange, save_screen


class TaskTests(unittest.TestCase):
    def test_deadline_requires_timezone(self):
        value = demo_task()
        value["deadline"] = "2026-11-07T20:00:00"
        with self.assertRaises(ValueError):
            Task.parse(value)

    def test_bad_scope_and_unknown_fields(self):
        for patch in ({"allowed_apps": []}, {"allowed_domains": ["https://school.test"]},
                      {"allowed_effects": ["shell"]}, {"mode": "anything"},
                      {"reserve_seconds": True}, {"surprise": "ignored?"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                Task.parse({**demo_task(), **patch})

    def test_scope_is_exact_not_suffix(self):
        task = Task.parse({**demo_task(), "allowed_domains": ["school.test"]})
        check_scope(task, {"app": "assignment-demo", "url": "https://school.test/course"})
        for url in ("https://school.test.evil.test", "https://evil.test/school.test", "file:///tmp/x"):
            with self.subTest(url=url), self.assertRaises(Stopped):
                check_scope(task, {"app": "assignment-demo", "url": url})

    def test_overlay_sandbox_cannot_widen_scope(self):
        value = {**demo_task(), "mode": "live", "environment": "sandbox"}
        self.assertEqual(Task.parse(value).environment, "sandbox")
        for patch in ({"allowed_apps": ["com.apple.Terminal"]}, {"allowed_domains": ["school.test"]},
                      {"allowed_effects": ["read", "purchase"]}, {"environment": "unrestricted"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                Task.parse({**value, **patch})

    def test_monotonic_budget_reserves_review_time(self):
        now = datetime.now(timezone.utc)
        ticks = [100.0]
        task = Task.parse({**demo_task(), "deadline": (now + timedelta(seconds=600)).isoformat()})
        budget = Budget(task, now=now, clock=lambda: ticks[0])
        self.assertEqual(budget.working(), 300)
        ticks[0] += 301
        with self.assertRaises(Stopped):
            budget.check()
        budget.check(reserve=False)  # Read-only completion verification still has time.
        budget.cancelled = True
        with self.assertRaises(Stopped):
            budget.check(reserve=False)

    def test_no_completion_without_all_independent_checks(self):
        task = Task.parse(demo_task())
        for result in ({"checks": []}, {"checks": [{"id": "draft_saved", "passed": True, "evidence": "saved"}]},
                       {"checks": [{"id": c["id"], "passed": True, "evidence": ""} for c in task.success_criteria]}):
            with self.subTest(result=result), self.assertRaises(Stopped):
                validate_verification(task, result)

    def test_required_verification_cannot_be_removed(self):
        plan = assignment_plan()
        plan["steps"] = [s for s in plan["steps"] if s["kind"] != "verify"]
        with self.assertRaises(ValueError):
            validate_plan(plan)


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.events = Events(Path(self.tmp.name))
        self.budget = Budget(Task.parse(demo_task()))

    def tearDown(self):
        self.tmp.cleanup()

    def test_request_ack_is_single_use_and_bound(self):
        exchange = Exchange(self.events, self.budget)
        result = []
        thread = threading.Thread(target=lambda: result.append(exchange.request("screenshot", {}, timeout=2)))
        thread.start()
        end = time.monotonic() + 2
        while exchange.pending is None and time.monotonic() < end:
            time.sleep(0.005)
        request_id = exchange.pending["id"]
        with self.assertRaises(ValueError):
            exchange.answer("wrong", {})
        exchange.answer(request_id, {"ok": True})
        thread.join(2)
        self.assertEqual(result, [{"ok": True}])
        with self.assertRaises(ValueError):
            exchange.answer(request_id, {"ok": True})

    def test_cancel_interrupts_pending_approval(self):
        approval = Approvals(self.events, self.budget)
        errors = []
        def waiting():
            try:
                approval.ask({"summary": "Submit fixture", "effect": "submit"})
            except Stopped as exc:
                errors.append(str(exc))
        thread = threading.Thread(target=waiting)
        thread.start()
        while not approval.pending:
            time.sleep(0.005)
        old_id = approval.pending["id"]
        self.budget.cancelled = True
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors)
        with self.assertRaises(ValueError):
            approval.answer(old_id, True)

    def test_screenshot_rejects_non_png_and_remote_urls(self):
        for value in ("https://site.test/image.png", "data:image/png;base64,bm90LXBuZw=="):
            with self.assertRaises(ValueError):
                save_screen(Path(self.tmp.name), value)


class DriverTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Session(Task.parse(demo_task()), Path(self.tmp.name))
        self.calls = []
        self.preflight = {"allowed": True, "effect": "edit", "token": "bound-token",
                          "state_id": "1", "summary": "Edit answer", "scope": {"app": "assignment-demo", "url": None}}
        outer = self
        class FakeExchange:
            def request(self, operation, arguments, **kwargs):
                outer.calls.append((operation, arguments))
                if operation == "preflight":
                    return outer.preflight.copy()
                return {"executed": True, "scope": {"app": "assignment-demo", "url": None}}
        self.driver = ComputerDriver(self.session, FakeExchange(), 0)
        self.driver.width, self.driver.height = 1024, 768

    def tearDown(self):
        self.tmp.cleanup()

    async def test_preflight_token_and_state_are_forwarded(self):
        await self.driver.type(action("type", text="My own answer"))
        self.assertEqual([c[0] for c in self.calls], ["preflight", "execute"])
        self.assertEqual(self.calls[-1][1]["preflight_token"], "bound-token")
        self.assertEqual(self.calls[-1][1]["state_id"], "1")

    async def test_unknown_effect_never_executes(self):
        self.preflight["effect"] = "unknown"
        with self.assertRaises(Stopped):
            await self.driver.click(action("click", x=10, y=10, button="left"))
        self.assertEqual(len(self.calls), 1)

    async def test_submit_waits_for_explicit_approval(self):
        self.preflight["effect"] = "submit"
        pending = asyncio.create_task(self.driver.click(action("click", x=10, y=10, button="left")))
        for _ in range(100):
            if self.session.approvals.pending:
                break
            await asyncio.sleep(0.005)
        self.assertTrue(self.session.approvals.pending)
        self.assertNotIn("execute", [c[0] for c in self.calls])
        self.session.approvals.answer(self.session.approvals.pending["id"], True)
        await pending
        self.assertEqual(self.calls[-1][0], "execute")

    async def test_decline_blocks_submission(self):
        self.preflight["effect"] = "submit"
        pending = asyncio.create_task(self.driver.click(action("click", x=10, y=10, button="left")))
        while not self.session.approvals.pending:
            await asyncio.sleep(0.005)
        self.session.approvals.answer(self.session.approvals.pending["id"], False)
        with self.assertRaises(PermissionError):
            await pending
        self.assertNotIn("execute", [c[0] for c in self.calls])

    async def test_chat_during_approval_revokes_proposed_action(self):
        self.preflight["effect"] = "submit"
        pending = asyncio.create_task(self.driver.click(action("click", x=10, y=10, button="left")))
        while not self.session.approvals.pending:
            await asyncio.sleep(0.005)
        approval_id = self.session.approvals.pending["id"]
        self.session.chat("잠깐, 파일을 먼저 수정해줘")
        try:
            self.session.approvals.answer(approval_id, True)
        except ValueError:
            pass  # The newer message already expired this approval.
        with self.assertRaises(ReplanRequested):
            await pending
        self.assertNotIn("execute", [c[0] for c in self.calls])

    async def test_chat_interrupts_approval_without_needing_a_decision(self):
        self.preflight["effect"] = "submit"
        pending = asyncio.create_task(self.driver.click(action("click", x=10, y=10, button="left")))
        while not self.session.approvals.pending:
            await asyncio.sleep(0.005)
        self.session.chat("제출을 미루고 내용부터 수정해줘")
        with self.assertRaises(ReplanRequested):
            await asyncio.wait_for(pending, 1)
        self.assertIsNone(self.session.approvals.pending)
        self.assertNotIn("execute", [c[0] for c in self.calls])

    async def test_out_of_bounds_action_never_reaches_host(self):
        with self.assertRaises(Stopped):
            await self.driver.click(action("click", x=2048, y=10, button="left"))
        self.assertFalse(self.calls)


class LearningTests(unittest.TestCase):
    def test_consent_gates_export_and_memory_and_no_split_leak(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = LearningStore(root)
            sessions = []
            for consent in (True, True, False):
                session = Session(Task.parse(demo_task()), root)
                session.plan = assignment_plan()
                session.planner_input = task_input(session.task, 3600, ["내가 올린 파일을 먼저 확인"])
                store.review(session, assignment_plan(), "자료 확인을 먼저 하기", consent)
                sessions.append(session)
            out = root / "dataset"
            manifest = store.export(out)
            self.assertEqual(manifest["train"] + manifest["validation"], 2)
            self.assertEqual(manifest["excluded"], 1)
            self.assertEqual(manifest["group_overlap"], 0)
            self.assertFalse(manifest["weights_trained"])
            # Identical assignment retries with different due dates are one group.
            self.assertTrue(manifest["train"] == 0 or manifest["validation"] == 0)
            self.assertEqual(len(store.examples("assignment_submission", sessions[0].id)), 1)
            self.assertEqual(store.examples("email", "none"), [])
            rows = (out / "train.jsonl").read_text() + (out / "validation.jsonl").read_text()
            self.assertNotIn("image_url", rows)
            self.assertNotIn("preflight_token", rows)
            first = json.loads(rows.splitlines()[0])
            self.assertEqual(json.loads(first["messages"][1]["content"])["user_messages"],
                             ["내가 올린 파일을 먼저 확인"])


if __name__ == "__main__":
    unittest.main()
