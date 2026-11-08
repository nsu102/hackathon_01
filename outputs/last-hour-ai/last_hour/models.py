from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
import math
import time


class Stopped(RuntimeError):
    pass


@dataclass
class Task:
    goal: str
    deadline: str
    context: str
    allowed_apps: list[str]
    allowed_domains: list[str]
    success_criteria: list[dict]
    allowed_effects: list[str]
    mode: str = "live"
    task_family: str = "assignment_submission"
    reserve_seconds: int = 300
    environment: str = "bridge"

    @classmethod
    def parse(cls, data: dict) -> Task:
        if not isinstance(data, dict):
            raise ValueError("Task must be a JSON object")
        allowed = set(cls.__dataclass_fields__)
        if set(data) - allowed:
            raise ValueError("Unknown task fields: " + ", ".join(sorted(set(data) - allowed)))
        try:
            task = cls(**data)
        except TypeError as exc:
            raise ValueError("Missing or invalid task fields") from exc
        for name, maximum in (("goal", 4000), ("context", 40000), ("task_family", 100)):
            value = getattr(task, name)
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"Invalid {name}")
        if task.mode not in ("live", "rehearsal"):
            raise ValueError("mode must be live or rehearsal")
        if task.environment not in ("bridge", "sandbox"):
            raise ValueError("environment must be bridge or sandbox")
        for name in ("allowed_apps", "allowed_domains", "allowed_effects"):
            value = getattr(task, name)
            if not isinstance(value, list) or len(value) > 100 or any(
                not isinstance(x, str) or not x.strip() or len(x) > 255 for x in value
            ):
                raise ValueError(f"Invalid {name}")
        if not task.allowed_apps:
            raise ValueError("Explicit allowed_apps required")
        if not set(task.allowed_effects) <= {"read", "navigate", "edit", "submit", "send", "delete", "purchase"}:
            raise ValueError("Unsupported allowed_effects")
        if "read" not in task.allowed_effects:
            raise ValueError("read effect required")
        task.allowed_domains = [x.lower() for x in task.allowed_domains]
        if any(urlparse("https://" + x).hostname != x or "/" in x or ":" in x
               for x in task.allowed_domains):
            raise ValueError("Domains must be exact hostnames, without scheme or port")
        if type(task.reserve_seconds) is not int or not 5 <= task.reserve_seconds <= 900:
            raise ValueError("reserve_seconds must be 5..900")
        if not isinstance(task.success_criteria, list) or not 1 <= len(task.success_criteria) <= 20:
            raise ValueError("1..20 success criteria required")
        ids = []
        for criterion in task.success_criteria:
            if (not isinstance(criterion, dict) or set(criterion) != {"id", "description"}
                or not all(isinstance(v, str) and 0 < len(v) <= 1000 for v in criterion.values())):
                raise ValueError("Each criterion needs id and description strings")
            ids.append(criterion["id"])
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate criterion ids")
        if task.environment == "sandbox" and (
            task.allowed_apps != ["assignment-demo"] or task.allowed_domains
            or set(ids) != {"draft_saved", "submission_receipt"}
            or not set(task.allowed_effects) <= {"read", "edit", "submit"}
        ):
            raise ValueError("Sandbox tasks require the isolated assignment-demo scope and criteria")
        task.due_at()  # Reject naive or malformed timestamps before dispatch.
        return task

    def due_at(self) -> datetime:
        try:
            result = datetime.fromisoformat(self.deadline.replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("deadline must be an ISO 8601 timestamp") from exc
        if result.tzinfo is None:
            raise ValueError("deadline must include a timezone, e.g. +09:00")
        return result

    def to_dict(self) -> dict:
        return asdict(self)


class Budget:
    def __init__(self, task: Task, *, now=None, clock=time.monotonic):
        self.clock = clock
        self.start = clock()
        self.total = (task.due_at() - (now or datetime.now(timezone.utc))).total_seconds()
        if not math.isfinite(self.total) or self.total <= 0:
            raise ValueError("Deadline has already passed")
        self.reserve = task.reserve_seconds
        self.cancelled = False

    def remaining(self) -> float:
        return max(0.0, self.total - (self.clock() - self.start))

    def working(self) -> float:
        return max(0.0, self.remaining() - self.reserve)

    def check(self, *, reserve=True):
        if self.cancelled:
            raise Stopped("User cancelled the task")
        if (self.working() if reserve else self.remaining()) <= 0:
            raise Stopped("Review reserve reached" if reserve else "Deadline reached")


def check_scope(task: Task, scope: dict):
    if not isinstance(scope, dict) or scope.get("app") not in task.allowed_apps:
        raise Stopped("Active app is outside the task scope")
    url = scope.get("url")
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http") or parsed.hostname not in task.allowed_domains:
            raise Stopped("Active domain is outside the task scope")


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or set(plan) != {"summary", "steps", "fallback"}:
        raise ValueError("Plan needs summary, steps, fallback")
    for field in ("summary", "fallback"):
        if not isinstance(plan[field], str) or not 1 <= len(plan[field]) <= 2000:
            raise ValueError(f"Invalid plan {field}")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        raise ValueError("Plan needs 1..8 steps")
    for step in steps:
        if (not isinstance(step, dict) or set(step) != {"title", "kind", "required"}
            or not isinstance(step["title"], str) or not 1 <= len(step["title"]) <= 500
            or step["kind"] not in ("inspect", "prepare", "act", "commit", "verify")
            or type(step["required"]) is not bool):
            raise ValueError("Invalid plan step")
    if not any(s["kind"] == "verify" and s["required"] for s in steps):
        raise ValueError("A required verification step is mandatory")
    return plan


def validate_verification(task: Task, value: dict) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
        raise Stopped("Host did not provide verification checks")
    checks = value["checks"]
    expected = {c["id"] for c in task.success_criteria}
    if len(checks) != len(expected) or {c.get("id") for c in checks if isinstance(c, dict)} != expected:
        raise Stopped("Host verification does not match the requested criteria")
    for check in checks:
        if (check.get("passed") is not True or not isinstance(check.get("evidence"), str)
            or not check["evidence"].strip() or len(check["evidence"]) > 4000):
            raise Stopped("Completion evidence missing or a criterion failed")
    return value
