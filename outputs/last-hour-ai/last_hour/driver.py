from __future__ import annotations

import asyncio
from types import SimpleNamespace

from .models import Stopped, check_scope, validate_verification
from .storage import save_screen


class ReplanRequested(RuntimeError):
    pass


class ComputerDriver:
    """OpenAI async computer driver backed by the overlay's trusted native host.

    The model proposes actions. The host classifies effects and binds execution to
    the inspected target. The server grants one-use approval for protected effects.
    """

    def __init__(self, session, exchange, revision):
        self.session, self.exchange, self.revision = session, exchange, revision
        self.width = self.height = 0

    def checkpoint(self):
        self.session.budget.check()
        if self.session.revision != self.revision:
            raise ReplanRequested("New user instructions arrived")

    async def rpc(self, operation, arguments, *, reserve=True):
        return await asyncio.to_thread(self.exchange.request, operation, arguments, reserve=reserve)

    async def allowed(self, action):
        self.checkpoint()
        return True

    async def approve_checks(self, call):
        self.checkpoint()
        checks = [check.model_dump(exclude_none=True) for check in call.pending_safety_checks]
        await asyncio.to_thread(self.session.approvals.ask, {
            "effect": "api_safety", "summary": "Computer Use API의 추가 확인 요청",
            "state_id": call.call_id, "checks": checks,
        }, self.checkpoint)
        self.checkpoint()
        return True

    async def screenshot(self):
        self.checkpoint()
        result = await self.rpc("screenshot", {})
        check_scope(self.session.task, result.get("scope"))
        self.width, self.height = result.get("width"), result.get("height")
        if any(type(n) is not int or not 1 <= n <= 16000 for n in (self.width, self.height)):
            raise Stopped("Host did not supply valid screenshot dimensions")
        screen_id, _ = save_screen(self.session.folder, result.get("image_url"))
        self.session.events.emit("computer.screen", screen_id=screen_id,
                                 width=self.width, height=self.height, scope=result["scope"])
        return {"type": "computer_screenshot", "image_url": result["image_url"]}

    async def perform(self, action):
        self.checkpoint()
        data = action.model_dump(exclude_none=True) if hasattr(action, "model_dump") else vars(action).copy()
        kind = data.get("type")
        if kind not in {"click", "double_click", "drag", "keypress", "move", "scroll", "type", "wait"}:
            raise Stopped("Unsupported computer action")
        if kind == "type" and (not isinstance(data.get("text"), str) or len(data["text"]) > 30000):
            raise Stopped("Typing action exceeds its limit")
        for point in ([data] if kind in {"click", "double_click", "move", "scroll"}
                      else data.get("path", []) if kind == "drag" else []):
            x, y = point.get("x"), point.get("y")
            if (type(x) not in (int, float) or type(y) not in (int, float)
                or not 0 <= x < self.width or not 0 <= y < self.height):
                raise Stopped("Action coordinates are outside the last screenshot")
        self.session.action_count += 1
        if self.session.action_count > self.session.max_actions:
            raise Stopped("Computer action budget exhausted")
        preflight = await self.rpc("preflight", {"action": data})
        check_scope(self.session.task, preflight.get("scope"))
        effect = preflight.get("effect")
        if preflight.get("allowed") is not True or effect not in self.session.task.allowed_effects:
            raise Stopped("Host refused the target or its effect is outside task permissions")
        if not all(isinstance(preflight.get(k), str) and 0 < len(preflight[k]) <= 2000
                   for k in ("token", "state_id", "summary")):
            raise Stopped("Host must bind a preflight token to a target and state")
        if effect in {"submit", "send", "delete", "purchase"}:
            await asyncio.to_thread(self.session.approvals.ask, {
                "effect": effect, "summary": preflight["summary"],
                "state_id": preflight["state_id"], "action": data,
            }, self.checkpoint)
        self.checkpoint()  # A message/cancel while approving invalidates this action.
        result = await self.rpc("execute", {
            "action": data, "preflight_token": preflight["token"],
            "state_id": preflight["state_id"],
        })
        if result.get("executed") is not True:
            raise Stopped("Host did not confirm bound execution")
        check_scope(self.session.task, result.get("scope"))
        self.session.events.emit("computer.action", action_type=kind, effect=effect,
                                 summary=preflight["summary"], count=self.session.action_count)

    async def click(self, action):
        await self.perform(action)

    async def double_click(self, action):
        await self.perform(action)

    async def drag(self, action):
        await self.perform(action)

    async def keypress(self, action):
        await self.perform(action)

    async def move(self, action):
        await self.perform(action)

    async def scroll(self, action):
        await self.perform(action)

    async def type(self, action):
        await self.perform(action)

    async def wait(self, action):
        await self.perform(action)

    async def verify(self):
        # Verification may use the reserved period; new side effects may not.
        self.session.budget.check(reserve=False)
        result = await self.rpc("verify", {"criteria": self.session.task.success_criteria}, reserve=False)
        self.session.budget.check(reserve=False)
        return validate_verification(self.session.task, result)


def action(kind, **kwargs):
    return SimpleNamespace(type=kind, **kwargs)
