"""A deterministic integration fixture, not an AI model or a real LMS integration."""
from __future__ import annotations

import asyncio
import base64
import json
import hashlib
import threading

from .driver import ComputerDriver, action
from .policy import assignment_plan, task_input
from .storage import write_json


PAGE = """<!doctype html><html lang="ko"><meta charset="utf-8">
<title>과제 제출 테스트 환경</title>
<style>body{font:16px system-ui;margin:40px;max-width:880px;color:#222}
textarea{display:block;width:100%;height:240px;font:16px system-ui;margin:16px 0}
button{padding:12px 24px;margin-right:12px}output{display:block;margin-top:24px}</style>
<h1>학습 계획 과제 · 테스트 환경</h1>
<p>외부 학교 시스템과 연결되지 않은 가상 제출함입니다.</p>
<p>요구사항: 본인이 작성한 학습 계획을 저장하고 제출하세요.</p>
<label for="answer">제출 내용</label><textarea id="answer"></textarea>
<button id="save">초안 저장</button><button id="submit">과제 제출</button>
<output id="status" aria-live="polite">아직 제출하지 않았습니다.</output>
<script>
window.saved = ''; window.receipt = '';
document.querySelector('#save').onclick = () => {
 window.saved = document.querySelector('#answer').value;
 document.querySelector('#status').textContent = '초안이 저장되었습니다.';
};
document.querySelector('#submit').onclick = () => {
 if (!window.saved || window.saved !== document.querySelector('#answer').value) return;
 window.receipt = 'DEMO-RECEIPT-001';
 document.querySelector('#status').textContent = '제출 완료 · 접수증 ' + window.receipt;
};
</script></html>"""


class PortalHost:
    """Trusted test host: knows every control and rejects unclassified actions."""
    def __init__(self, session):
        self.session = session
        self.scope = {"app": "assignment-demo", "url": None}
        self.version = 0
        self.tokens = {}
        self.controls = {}
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def handle(self, page, operation, arguments):
        if page.url != "about:blank":
            return {"error": "Fixture page left the isolated environment"}
        def state_id():
            state = page.evaluate("""() => ({text: document.querySelector('#answer').value,
                saved: window.saved, receipt: window.receipt, focus: document.activeElement.id,
                controls: ['answer','save','submit'].map(id => {
                  const b = document.getElementById(id).getBoundingClientRect();
                  return [id,b.x,b.y,b.width,b.height]; })})""")
            return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        if operation == "screenshot":
            raw = page.screenshot(type="png")
            return {"image_url": "data:image/png;base64," + base64.b64encode(raw).decode(),
                    "width": 1024, "height": 768, "scope": self.scope}
        if operation == "preflight":
            act = arguments["action"]
            target = None
            if act["type"] == "click" and act.get("button", "left") == "left":
                for name in self.controls:
                    box = page.locator("#" + name).bounding_box()
                    if box["x"] <= act["x"] < box["x"] + box["width"] and box["y"] <= act["y"] < box["y"] + box["height"]:
                        target = name
            elif act["type"] == "type" and page.locator("#answer").evaluate("el => el === document.activeElement"):
                target = "typing"
            elif act["type"] == "keypress" and page.locator("#answer").evaluate("el => el === document.activeElement"):
                keys = [str(key).upper() for key in act.get("keys", [])]
                if keys in (["META", "A"], ["CMD", "A"], ["CONTROL", "A"], ["CTRL", "A"], ["BACKSPACE"], ["DELETE"]):
                    target = "editing_keys"
            elif act["type"] == "wait":
                target = "wait"
            if target is None:
                return {"allowed": False, "scope": self.scope}
            effect = "submit" if target == "submit" else "read" if target == "wait" else "edit"
            import uuid
            token = uuid.uuid4().hex
            state = state_id()
            self.tokens.clear()
            self.tokens[token] = (state, act, target)
            return {"allowed": True, "effect": effect, "token": token, "state_id": state,
                    "scope": self.scope, "summary": "가상 과제함에 최종 제출" if target == "submit" else "가상 과제 초안 편집"}
        if operation == "execute":
            bound = self.tokens.pop(arguments["preflight_token"], None)
            if bound is None or bound[0] != state_id() or bound[0] != arguments["state_id"] or bound[1] != arguments["action"]:
                return {"error": "Stale or mismatched preflight token"}
            act = bound[1]
            if act["type"] == "click":
                page.mouse.click(act["x"], act["y"])
            elif act["type"] == "type":
                # insert_text is a real browser keyboard operation, not DOM fill.
                if not page.locator("#answer").evaluate("el => el === document.activeElement"):
                    return {"error": "Focus changed"}
                page.keyboard.insert_text(act["text"])
            elif act["type"] == "keypress":
                keys = [str(key).upper() for key in act["keys"]]
                if len(keys) == 2:
                    page.keyboard.press("Meta+a" if keys[0] in {"META", "CMD"} else "Control+a")
                else:
                    page.keyboard.press("Backspace" if keys[0] == "BACKSPACE" else "Delete")
            elif act["type"] == "wait":
                page.wait_for_timeout(100)
            self.version += 1
            if bound[2] == "save":
                (self.session.folder / "draft.txt").write_text(page.evaluate("window.saved"), encoding="utf-8")
            return {"executed": True, "scope": self.scope, "state_id": str(self.version)}
        if operation == "verify":
            saved = page.evaluate("window.saved")
            receipt = page.evaluate("window.receipt")
            (self.session.folder / "draft.txt").write_text(saved, encoding="utf-8")
            observations = {
                "draft_saved": {"id": "draft_saved", "passed": saved == self.session.task.context,
                                "evidence": "가상 제출함의 저장 내용이 사용자 제공 원문과 일치합니다."},
                "submission_receipt": {"id": "submission_receipt", "passed": receipt == "DEMO-RECEIPT-001",
                                       "evidence": receipt or "접수증 없음"},
            }
            return {"checks": [observations.get(c["id"], {"id": c["id"], "passed": False, "evidence": "Unknown fixture criterion"})
                               for c in arguments["criteria"]], "environment": "local_fixture"}
        return {"error": "Unsupported fixture operation"}

    def run(self):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(env={}, chromium_sandbox=True)
                try:
                    page = browser.new_page(viewport={"width": 1024, "height": 768})
                    page.route("**/*", lambda route: route.abort())
                    page.set_content(PAGE)
                    for name in ("answer", "save", "submit"):
                        self.controls[name] = page.locator("#" + name).bounding_box()
                    self.ready.set()
                    cursor = 0
                    while not self.stop.is_set():
                        for event in self.session.events.read(cursor, wait=0.1):
                            cursor = event["seq"]
                            if event["type"] != "computer.request":
                                continue
                            request = event["data"]
                            try:
                                result = self.handle(page, request["operation"], request["arguments"])
                            except Exception as exc:
                                result = {"error": type(exc).__name__}
                            try:
                                self.session.exchange.answer(request["id"], result)
                            except ValueError:
                                pass  # Request was cancelled or expired.
                finally:
                    browser.close()
        except Exception as exc:
            self.error = str(exc)
            self.ready.set()


async def run_rehearsal(session):
    if (session.task.allowed_apps != ["assignment-demo"]
        or {c["id"] for c in session.task.success_criteria} != {"draft_saved", "submission_receipt"}):
        raise ValueError("Rehearsal requires the assignment-demo fixture scope and criteria")
    session.events.emit("chat.assistant", message="로컬 가상 과제함에서 고정 스크립트를 실행합니다. AI 추론·외부 제출·모델 학습은 수행하지 않습니다.")
    session.planner_input = task_input(session.task, session.budget.remaining())
    session.plan = assignment_plan()
    write_json(session.folder / "plan.json", session.plan)
    session.events.emit("plan.ready", plan=session.plan)
    session.transition("running")
    host = PortalHost(session)
    host.thread.start()
    try:
        await asyncio.to_thread(host.ready.wait, 15)
        if not host.ready.is_set() or host.error:
            raise RuntimeError("Rehearsal browser unavailable; install Chromium. " + (host.error or "Startup timeout"))
        driver = ComputerDriver(session, session.exchange, session.revision)
        await driver.screenshot()
        for name in ("answer", "save", "submit"):
            box = host.controls[name]
            await driver.click(action("click", x=box["x"] + box["width"] / 2,
                                      y=box["y"] + box["height"] / 2, button="left"))
            if name == "answer":
                await driver.type(action("type", text=session.task.context))
        await driver.screenshot()
        session.transition("verifying")
        session.verification = await driver.verify()
        session.transition("completed", message="가상 제출함의 저장 내용과 접수증을 검증했습니다. 실제 외부 제출은 없습니다.")
    finally:
        host.stop.set()
        await asyncio.to_thread(host.thread.join, 5)
