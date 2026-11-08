"""OpenRouter Chat Completions transport and a provider-neutral computer loop.

Only our guarded ComputerDriver executes effects. No native OpenAI computer tool
or OpenAI account is needed for this path.
"""
from __future__ import annotations

import asyncio
import copy
import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .driver import action
from .models import Stopped


class ProviderError(RuntimeError):
    """Sanitized error safe to show in the overlay. Never includes upstream bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenRouterClient:
    def __init__(self, settings):
        self.settings = settings

    def _send(self, payload):
        request = Request(
            self.settings.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(),
            headers={"Authorization": "Bearer " + self.settings.api_key,
                     "Content-Type": "application/json", "X-OpenRouter-Title": "Last Hour AI"},
            method="POST",
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(4_000_001)
        except HTTPError as exc:
            hints = {401: "API key was rejected", 402: "Credit balance is insufficient",
                     403: "Model or provider access was denied", 404: "Model or API route was not found",
                     429: "Rate limit reached; retry after checking provider limits"}
            code = exc.code
            exc.close()
            raise ProviderError(f"OpenRouter HTTP {code}: {hints.get(code, 'Request failed')}") from None
        except (TimeoutError, URLError, OSError):
            raise ProviderError("OpenRouter connection failed or timed out") from None
        if len(raw) > 4_000_000:
            raise ProviderError("OpenRouter response exceeded the size limit")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ProviderError("OpenRouter returned invalid JSON") from None
        if not isinstance(result, dict) or result.get("error"):
            raise ProviderError("OpenRouter returned an API error")
        return result

    async def complete(self, *, model, messages, max_tokens=6144, tools=None, response_format=None):
        payload = {"model": model, "messages": messages, "stream": False, "max_tokens": max_tokens,
                   "provider": {"require_parameters": True},
                   "reasoning": {"effort": self.settings.reasoning_effort, "exclude": True}}
        if tools is not None:
            # Claude endpoints do not advertise parallel_tool_calls. With strict
            # provider routing, sending even False eliminates every endpoint (404).
            # Enforce one action locally before dispatching any effect instead.
            payload.update(tools=tools, tool_choice="auto")
        if response_format is not None:
            payload["response_format"] = response_format
        # No automatic retries: do not silently repeat requests around desktop effects.
        return await asyncio.to_thread(self._send, payload)


def assistant_message(response):
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("OpenRouter returned no completion choice")
    choice = choices[0]
    if choice.get("finish_reason") not in {"stop", "tool_calls"}:
        raise ProviderError("Model output was truncated, filtered or unfinished; no actions were executed")
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ProviderError("OpenRouter returned an invalid assistant message")
    if message.get("refusal"):
        raise ProviderError("Model declined this task; hand control back to the user")
    return message


def parse_object(text):
    if not isinstance(text, str):
        raise ProviderError("Model did not return JSON text")
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except ValueError:
        raise ProviderError("Model returned malformed JSON") from None
    if not isinstance(value, dict):
        raise ProviderError("Model output must be a JSON object")
    return value


def final_status(value):
    if (set(value) != {"status", "message"} or value.get("status") not in
        {"needs_input", "ready_for_verification", "handoff"}
        or not isinstance(value.get("message"), str) or not 1 <= len(value["message"]) <= 4000):
        raise ProviderError("Model returned an invalid final task status")
    return value


def record_usage(session, response, *, stage, model):
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return
    clean = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
             if type(usage.get(key)) is int and usage[key] >= 0}
    cost = usage.get("cost")
    if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
        clean["cost_usd"] = cost
    session.events.emit("model.usage", provider="openrouter", model=model, stage=stage, **clean)


def validate_action(value):
    if not isinstance(value, dict):
        raise ProviderError("computer_action requires an action object")
    kind = value.get("type")
    required = {
        "screenshot": set(), "click": {"x", "y", "button"}, "double_click": {"x", "y"},
        "move": {"x", "y"}, "scroll": {"x", "y", "scroll_x", "scroll_y"},
        "drag": {"path"}, "keypress": {"keys"}, "type": {"text"}, "wait": set(),
    }
    if not isinstance(kind, str) or kind not in required:
        raise ProviderError("Unsupported computer action type")
    optional = {"keys"} if kind in {"click", "double_click", "move", "scroll", "drag"} else set()
    fields = set(value) - {"type"}
    if not required[kind] <= fields or fields - required[kind] - optional:
        raise ProviderError("Computer action fields do not match its type")
    for key in ("x", "y", "scroll_x", "scroll_y"):
        if key in value and (type(value[key]) is not int or abs(value[key]) > 32000):
            raise ProviderError("Computer coordinates and scroll deltas must be bounded integers")
    if "keys" in value and (not isinstance(value["keys"], list) or len(value["keys"]) > 8
        or any(not isinstance(k, str) or not 1 <= len(k) <= 40 for k in value["keys"])):
        raise ProviderError("Invalid computer key combination")
    if kind == "keypress" and not value["keys"]:
        raise ProviderError("A keypress must contain keys")
    if kind == "click" and value["button"] not in {"left", "right", "wheel", "back", "forward"}:
        raise ProviderError("Unsupported mouse button")
    if kind == "type" and (not isinstance(value["text"], str) or len(value["text"]) > 30000):
        raise ProviderError("Invalid text for typing")
    if kind == "drag":
        if not isinstance(value["path"], list) or not 2 <= len(value["path"]) <= 100:
            raise ProviderError("A drag requires 2..100 points")
        for point in value["path"]:
            if (not isinstance(point, dict) or set(point) != {"x", "y"}
                or any(type(n) is not int or abs(n) > 32000 for n in point.values())):
                raise ProviderError("Invalid drag point")
    return value


TOOLS = [
    {"type": "function", "function": {
        "name": "computer_action", "description": "Request one guarded computer action in screenshot pixel coordinates. Re-observe after each action. Never bypass a refused target.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["action"], "properties": {
            "action": {"type": "object", "additionalProperties": False, "required": ["type"], "properties": {
                "type": {"type": "string", "enum": ["screenshot", "click", "double_click", "move", "scroll", "drag", "keypress", "type", "wait"]},
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "button": {"type": "string", "enum": ["left", "right", "wheel", "back", "forward"]},
                "keys": {"type": "array", "items": {"type": "string"}}, "text": {"type": "string"},
                "scroll_x": {"type": "integer"}, "scroll_y": {"type": "integer"},
                "path": {"type": "array", "items": {"type": "object", "required": ["x", "y"],
                    "additionalProperties": False, "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}}},
            }},
        }},
    }},
    {"type": "function", "function": {
        "name": "finish", "description": "Stop acting, ask the user for missing input, or request independent host verification. This does not certify completion.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["status", "message"],
            "properties": {"status": {"type": "string", "enum": ["needs_input", "ready_for_verification", "handoff"]},
                           "message": {"type": "string"}}},
    }},
    {"type": "function", "function": {
        "name": "progress", "description": "Show a brief observable progress update in the overlay, without hidden reasoning.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["message"],
                       "properties": {"message": {"type": "string"}}},
    }},
]


EXECUTOR_RULES = """
Use the computer_action function one action per turn; each action is independently
checked by the host. Use image-pixel coordinates, not normalized coordinates. The
action fields are: screenshot/wait: type only; click: type,x,y,button,optional keys;
double_click/move: type,x,y,optional keys; type: type,text; keypress: type,keys;
scroll: type,x,y,scroll_x,scroll_y,optional keys; drag: type,path,optional keys.
Observe the returned screenshot after each action. A new screenshot is provided
before the first turn. Do not repeat an action based on a stale screenshot.
Report short progress with progress(), then continue. If a prerequisite is missing,
use finish(status='needs_input', message='a short question'). If ready, use
finish(status='ready_for_verification', message='observable progress'). If blocked,
use finish(status='handoff', message='saved work and remaining steps').
Never emit more than one tool call in a turn. Never self-certify completion.
"""


def observation(session, driver, screen):
    return {"role": "user", "content": [
        {"type": "text", "text": json.dumps({"observation": "current screenshot", "width": driver.width,
            "height": driver.height, "seconds_remaining": int(session.budget.remaining()),
            "review_reserve_seconds": session.budget.reserve}, ensure_ascii=False)},
        {"type": "image_url", "image_url": {"url": screen["image_url"]}},
    ]}


def limit_images(messages, keep=3):
    result = copy.deepcopy(messages)
    images = [(message, index) for message in result if isinstance(message.get("content"), list)
              for index, item in enumerate(message["content"]) if item.get("type") == "image_url"]
    for message, index in images[:-keep]:
        message["content"][index] = {"type": "text", "text": "Earlier screenshot omitted; use the current observation."}
    return result


async def execute_openrouter(session, driver, client, settings, rules):
    messages = [{"role": "system", "content": rules + "\n" + EXECUTOR_RULES},
                {"role": "user", "content": json.dumps({"task": session.task.to_dict(), "plan": session.plan,
                    "user_messages": list(session.messages)}, ensure_ascii=False)}]

    async def observe():
        screen = await driver.screenshot()
        # Observation metadata comes from our driver, never from model text.
        messages.append(observation(session, driver, screen))

    await observe()
    seen_call_ids = set()
    for _ in range(session.max_steps):
        driver.checkpoint()
        messages[:] = limit_images(messages)
        response = await client.complete(model=settings.computer_model, messages=messages, tools=TOOLS)
        driver.checkpoint()
        record_usage(session, response, stage="computer", model=settings.computer_model)
        message = assistant_message(response)
        calls = message.get("tool_calls") or []
        if not isinstance(calls, list) or len(calls) > 1:
            raise ProviderError("Expected at most one tool call; no actions in the batch were executed")
        if not calls:
            return final_status(parse_object(message.get("content")))
        call = calls[0]
        if (not isinstance(call, dict) or call.get("type") != "function" or not isinstance(call.get("id"), str)
            or not call["id"] or call["id"] in seen_call_ids or not isinstance(call.get("function"), dict)):
            raise ProviderError("Invalid or repeated tool call; no action was executed")
        seen_call_ids.add(call["id"])
        function = call["function"]
        name = function.get("name")
        arguments = parse_object(function.get("arguments"))
        # Preserve provider reasoning signatures if present; never display them.
        messages.append({k: message[k] for k in ("role", "content", "tool_calls", "reasoning_details") if k in message})
        if name == "finish":
            return final_status(arguments)
        if name == "progress":
            if set(arguments) != {"message"} or not isinstance(arguments["message"], str) or not 1 <= len(arguments["message"]) <= 1000:
                raise ProviderError("Invalid progress update")
            session.events.emit("chat.assistant", message=arguments["message"])
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": "Progress displayed."})
            continue
        if name != "computer_action" or set(arguments) != {"action"}:
            raise ProviderError("Model requested an unknown tool; no action was executed")
        value = validate_action(arguments["action"])
        if value["type"] != "screenshot":
            await driver.perform(action(value["type"], **{k: v for k, v in value.items() if k != "type"}))
        messages.append({"role": "tool", "tool_call_id": call["id"],
                         "content": "Guarded action finished. Inspect the following current screenshot."})
        await observe()
    raise Stopped("OpenRouter tool-call step budget exhausted")
