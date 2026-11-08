from __future__ import annotations

import asyncio
import os
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from .config import ModelSettings
from .driver import ComputerDriver, ReplanRequested
from .models import Budget, Stopped, Task
from .policy import LearningStore, ModelPolicy, execute_live, task_input
from .openrouter import OpenRouterClient, ProviderError
from .storage import Approvals, Events, Exchange, write_json


TERMINAL = {"completed", "handoff", "cancelled", "failed", "deadline_stopped"}


@asynccontextmanager
async def model_client(settings):
    if settings.provider == "openrouter":
        yield OpenRouterClient(settings)
    else:
        from openai import AsyncOpenAI
        async with AsyncOpenAI(api_key=settings.api_key, timeout=30, max_retries=0) as client:
            yield client


class Session:
    def __init__(self, task: Task, root: Path, settings=None):
        self.id = uuid.uuid4().hex
        self.task, self.budget = task, Budget(task)
        self.settings = settings or ModelSettings.read()
        self.folder = root / "runs" / self.id
        self.events = Events(self.folder)
        self.exchange = Exchange(self.events, self.budget)
        self.approvals = Approvals(self.events, self.budget)
        self.learning = LearningStore(root)
        self.lock = threading.RLock()
        self.messages = []
        self.revision = 0
        self.action_count = 0
        self.max_actions, self.max_steps = 160, 48
        self.status = "created"
        self.plan = self.planner_input = self.verification = None
        self.worker = None
        self.monitor = None
        self.portal_host = None
        self.transition("created")

    def snapshot(self):
        with self.lock:
            return {
                "id": self.id, "status": self.status, "mode": self.task.mode,
                "goal": self.task.goal, "deadline": self.task.deadline,
                "seconds_remaining": round(self.budget.remaining(), 1),
                "reserve_seconds": self.budget.reserve, "action_count": self.action_count,
                "plan": self.plan, "verification": self.verification,
                "pending_computer_request": self.exchange.pending,
                "pending_approval": self.approvals.pending,
                "event_cursor": len(self.events.items),
                "model": self.settings.public(),
                "environment": self.task.environment,
            }

    def transition(self, status, **details):
        with self.lock:
            self.status = status
            self.events.emit("task.status", status=status, **details)
            write_json(self.folder / "task.json", self.task.to_dict())
            write_json(self.folder / "state.json", self.snapshot())

    def chat(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("message must contain 1..8000 characters")
        with self.lock:
            if self.status in TERMINAL:
                raise ValueError("Task is already finished; create another task")
            if len(self.messages) >= 50:
                raise ValueError("Chat message budget exhausted")
            self.messages.append(text)
            self.revision += 1
            self.events.emit("chat.user", message=text)

    def cancel(self):
        self.budget.cancelled = True
        self.events.emit("task.cancel_requested")
        if self.status in {"created", "waiting_input"}:
            self.transition("cancelled", message="사용자가 작업을 중지했습니다.")
            if self.portal_host:
                self.portal_host.stop.set()

    def start(self):
        with self.lock:
            if self.worker is not None and self.worker.is_alive():
                return
            self.worker = threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True)
            self.worker.start()
            if self.monitor is None:
                self.monitor = threading.Thread(target=self.watch_deadline, daemon=True)
                self.monitor.start()

    def watch_deadline(self):
        import time
        while self.status not in TERMINAL:
            with self.lock:
                if self.status == "waiting_input" and self.budget.working() <= 0:
                    self.transition("deadline_stopped", message="사용자 답변을 기다리는 동안 검토 예비 시간에 도달했습니다.")
                    if self.portal_host:
                        self.portal_host.stop.set()
                    return
            time.sleep(0.25)

    async def run(self):
        try:
            self.budget.check()
            if self.task.mode == "rehearsal":
                from .rehearsal import run_rehearsal
                await run_rehearsal(self)
                return
            if self.task.environment == "sandbox" and self.portal_host is None:
                from .rehearsal import PortalHost
                self.portal_host = PortalHost(self)
                self.portal_host.thread.start()
                await asyncio.to_thread(self.portal_host.ready.wait, 15)
                if not self.portal_host.ready.is_set() or self.portal_host.error:
                    raise ValueError("가상 과제함 실행 실패: Playwright와 Chromium 설치를 확인해주세요.")
                self.events.emit("chat.assistant", message="AI 모델이 격리된 가상 과제함에서 작업합니다. 실제 학교 제출은 없습니다.")
            async with model_client(self.settings) as client:
                for attempt in range(6):
                    self.budget.check()
                    revision = self.revision
                    self.planner_input = task_input(self.task, self.budget.remaining(), self.messages)
                    self.transition("planning")
                    self.plan = await asyncio.wait_for(
                        ModelPolicy().plan(self, client), timeout=min(40, self.budget.working()))
                    write_json(self.folder / "plan.json", self.plan)
                    self.events.emit("plan.ready", plan=self.plan)
                    driver = ComputerDriver(self, self.exchange, revision)
                    self.transition("running")
                    try:
                        result = await asyncio.wait_for(execute_live(self, driver, client),
                                                        timeout=self.budget.working())
                        driver.checkpoint()
                    except ReplanRequested:
                        self.events.emit("task.replanning", reason="새 사용자 메시지를 반영합니다.")
                        continue
                    self.events.emit("chat.assistant", message=result["message"])
                    if result["status"] == "needs_input":
                        with self.lock:
                            if revision != self.revision:
                                continue
                            self.transition("waiting_input", message=result["message"])
                        return
                    if result["status"] == "handoff":
                        self.transition("handoff", message=result["message"])
                        return
                    self.transition("verifying")
                    self.verification = await driver.verify()
                    self.transition("completed", message="호스트가 모든 완료 조건의 근거를 확인했습니다.")
                    return
                raise Stopped("Too many replans; hand control back to the user")
        except (Exception, asyncio.CancelledError) as exc:
            # Local diagnostics are opt-in and never sent over the overlay API.
            if os.getenv("LAST_HOUR_DEBUG") == "1":
                import traceback
                traceback.print_exc()
            if self.budget.cancelled:
                status = "cancelled"
            elif self.budget.working() <= 0:
                status = "deadline_stopped"
            else:
                status = "handoff" if isinstance(exc, (Stopped, PermissionError, TimeoutError)) else "failed"
            # SDK exceptions can contain request data. Keep them off the API/logs.
            safe = str(exc)[:500] if type(exc) in {Stopped, PermissionError, TimeoutError, ValueError, ProviderError} else type(exc).__name__
            self.transition(status, message=safe,
                            fallback=self.plan["fallback"] if self.plan else "현재 자료와 미완료 단계를 확인해주세요.")
        finally:
            if self.portal_host and self.status in TERMINAL:
                self.portal_host.stop.set()
                await asyncio.to_thread(self.portal_host.thread.join, 5)


class Service:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        from .study import StudyService
        self.study = StudyService(self.root)
        self.sessions = {}
        self.lock = threading.Lock()

    def create(self, data):
        task = Task.parse(data)
        settings = ModelSettings.read()
        if task.mode == "live":
            settings.require_key()
        if task.mode == "live" and settings.provider == "openai":
            try:
                from openai import AsyncComputerToolset, AsyncOpenAI  # noqa: F401
            except ImportError as exc:
                raise ValueError("Install the live extra: pip install -e '.[live]'") from exc
        with self.lock:
            if any(s.status not in TERMINAL for s in self.sessions.values()):
                raise ValueError("One desktop task at a time; finish or cancel the current task")
            session = Session(task, self.root, settings=settings)
            self.sessions[session.id] = session
            session.start()
            return session

    def get(self, task_id):
        with self.lock:
            try:
                return self.sessions[task_id]
            except KeyError as exc:
                raise ValueError("Unknown task id (in-flight runs are not resumed after server restart)") from exc
