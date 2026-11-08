from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import validate_plan
from .storage import write_json


RULES = Path(__file__).with_name("prompts.md").read_text(encoding="utf-8")
PLANNER_RULES = RULES + """

Return only a JSON object with exactly summary (string), fallback (string), and
steps (1..8 objects). Each step has title (string), kind (one of inspect, prepare,
act, commit, verify), required (boolean). At least one required verify step must
exist. Include a commit checkpoint when the task involves submission or sending.
Use the user's language. Never claim a plan has already been executed. Fallback
must say what useful draft and remaining instructions to hand over if time ends.
"""


def task_input(task, seconds, messages=None):
    return json.dumps({
        "task": task.to_dict(), "seconds_remaining": max(0, int(seconds)),
        "review_reserve_seconds": task.reserve_seconds,
        "user_messages": list(messages or []),
    }, ensure_ascii=False)


def assignment_plan():
    return validate_plan({
        "summary": "과제 안내 확인 → 초안 저장 → 제출 승인 → 접수증 검증",
        "steps": [
            {"title": "과제 요구사항과 제출 대상을 확인", "kind": "inspect", "required": True},
            {"title": "허용된 자료로 작성하고 초안을 저장", "kind": "prepare", "required": True},
            {"title": "사용자 승인 후 해당 과제에 제출", "kind": "commit", "required": True},
            {"title": "제출 상태와 접수증을 독립 검증", "kind": "verify", "required": True},
        ],
        "fallback": "저장된 초안과 아직 끝내지 못한 제출 단계를 사용자에게 전달합니다.",
    })


class LearningStore:
    def __init__(self, root: Path):
        self.folder = root / "reviews"
        self.folder.mkdir(parents=True, exist_ok=True)

    def review(self, session, corrected_plan, feedback, consent):
        if type(consent) is not bool or not isinstance(feedback, str) or len(feedback) > 8000:
            raise ValueError("Invalid review feedback or consent")
        if session.plan is None or session.planner_input is None:
            raise ValueError("Task has no plan to review yet")
        record = {
            "task_id": session.id, "task_family": session.task.task_family,
            "input": session.planner_input, "original_plan": session.plan,
            "corrected_plan": validate_plan(corrected_plan), "feedback": feedback,
            "consent_for_training": consent,
            "group": hashlib.sha256(json.dumps({
                "goal": session.task.goal, "context": session.task.context,
                "criteria": session.task.success_criteria,
            }, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        }
        write_json(self.folder / (session.id + ".json"), record)
        return record

    def examples(self, family, exclude_id):
        # Consent gates both reuse in subsequent API prompts and dataset export.
        records = []
        for path in sorted(self.folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            value = json.loads(path.read_text(encoding="utf-8"))
            if (value["consent_for_training"] is True and value["task_family"] == family
                and value["task_id"] != exclude_id):
                records.append(value)
            if len(records) == 3:
                break
        return records

    def export(self, output: Path):
        output.mkdir(parents=True, exist_ok=True)
        counts = {"train": 0, "validation": 0, "excluded": 0}
        rows = {"train": [], "validation": []}
        groups = {"train": set(), "validation": set()}
        for path in sorted(self.folder.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("consent_for_training") is not True:
                counts["excluded"] += 1
                continue
            # Repeated attempts on an assignment stay in the same split.
            split = "validation" if int(record["group"][:8], 16) % 5 == 0 else "train"
            rows[split].append({"messages": [
                {"role": "system", "content": PLANNER_RULES},
                {"role": "user", "content": record["input"]},
                {"role": "assistant", "content": json.dumps(record["corrected_plan"], ensure_ascii=False)},
            ]})
            groups[split].add(record["group"])
            counts[split] += 1
        for split in rows:
            (output / (split + ".jsonl")).write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows[split]), encoding="utf-8")
        manifest = {**counts, "group_overlap": len(groups["train"] & groups["validation"]),
                    "weights_trained": False, "uploaded": False,
                    "ready_for_evaluation": bool(counts["train"] and counts["validation"])}
        write_json(output / "manifest.json", manifest)
        return manifest


PLAN_FORMAT = {"type": "json_schema", "json_schema": {
    "name": "deadline_plan", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["summary", "steps", "fallback"],
        "properties": {
            "summary": {"type": "string"}, "fallback": {"type": "string"},
            "steps": {"type": "array", "minItems": 1, "maxItems": 8, "items": {
                "type": "object", "additionalProperties": False, "required": ["title", "kind", "required"],
                "properties": {"title": {"type": "string"}, "required": {"type": "boolean"},
                               "kind": {"type": "string", "enum": ["inspect", "prepare", "act", "commit", "verify"]}},
            }},
        },
    },
}}


class ModelPolicy:
    async def plan(self, session, client):
        messages = [{"role": "system", "content": PLANNER_RULES}]
        examples = session.learning.examples(session.task.task_family, session.id)
        for record in examples:
            messages.extend([
                {"role": "user", "content": record["input"]},
                {"role": "assistant", "content": json.dumps(record["corrected_plan"], ensure_ascii=False)},
            ])
        messages.append({"role": "user", "content": session.planner_input})
        settings = session.settings
        if settings.provider == "openrouter":
            from .openrouter import assistant_message, parse_object, record_usage
            response = await client.complete(model=settings.policy_model, messages=messages, response_format=PLAN_FORMAT)
            record_usage(session, response, stage="planning", model=settings.policy_model)
            message = assistant_message(response)
            if message.get("tool_calls"):
                raise ValueError("Planner must return a plan, not tool calls")
            plan = parse_object(message.get("content"))
        else:
            response = await client.responses.create(
                model=settings.policy_model, input=messages, store=False, max_output_tokens=2200,
            )
            plan = json.loads(response.output_text)
        session.events.emit("learning.context", approved_examples=len(examples),
                            method="in_context_examples", weights_trained=False)
        return validate_plan(plan)


async def execute_live(session, driver, client):
    if session.settings.provider == "openrouter":
        from .openrouter import execute_openrouter
        return await execute_openrouter(session, driver, client, session.settings, RULES)
    from openai import AsyncComputerToolset

    context = {
        "task": session.task.to_dict(), "plan": session.plan,
        "user_messages": session.messages,
        "seconds_remaining": int(session.budget.remaining()),
    }
    instruction = RULES + """

Operate using screenshots and computer actions. Take a screenshot first. If a
required fact is missing, finish with JSON {"status":"needs_input","message":"a short question"}.
If the work is ready for independent verification, finish with JSON
{"status":"ready_for_verification","message":"observable progress summary"}.
Otherwise finish with JSON {"status":"handoff","message":"what is saved and what remains"}.
Do not include markdown fences. You cannot self-certify success.

"""
    tools = AsyncComputerToolset(driver)
    try:
        response = await tools.run(
            client, {"model": session.settings.computer_model,
                     "store": False, "instructions": instruction,
                     "input": json.dumps(context, ensure_ascii=False), "max_output_tokens": 1800},
            before_action=driver.allowed, approve_safety_checks=driver.approve_checks,
            cancelled=lambda: session.budget.cancelled, max_steps=session.max_steps,
        )
        try:
            value = json.loads(response.output_text)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Executor did not return the required final status") from exc
        if (not isinstance(value, dict) or value.get("status") not in
            {"needs_input", "ready_for_verification", "handoff"}
            or not isinstance(value.get("message"), str) or len(value["message"]) > 4000):
            raise RuntimeError("Invalid executor final status")
        return value
    finally:
        tools.close()
