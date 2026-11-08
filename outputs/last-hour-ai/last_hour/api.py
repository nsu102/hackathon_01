from __future__ import annotations

import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .config import ModelSettings
from .openrouter import ProviderError
from .tutor_model import TutorModel
from .engine import Service, TERMINAL


MAX_BODY = 15_000_000


def make_handler(service, token, allowed_origin):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            pass  # Do not log chat, screenshots, task content or bearer tokens.

        def headers_for(self, content_type="application/json"):
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if allowed_origin and self.headers.get("Origin") == allowed_origin:
                self.send_header("Access-Control-Allow-Origin", allowed_origin)
                self.send_header("Vary", "Origin")

        def reply(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.headers_for()
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            origin = self.headers.get("Origin")
            if origin and origin != allowed_origin:
                self.reply(403, {"error": "Origin is not allowed"})
                self.close_connection = True
                return False
            actual = self.headers.get("Authorization", "")
            if not hmac.compare_digest(actual, "Bearer " + token):
                self.reply(401, {"error": "Bearer token required"})
                self.close_connection = True
                return False
            return True

        def do_OPTIONS(self):
            if not allowed_origin or self.headers.get("Origin") != allowed_origin:
                self.reply(403, {"error": "Origin is not allowed"})
                return
            self.send_response(204)
            self.headers_for()
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Last-Event-ID")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

        def study_dispatch(self, method, parts):
            study = service.study
            if method == "GET" and parts == ["heart"]:
                self.reply(200, study.heart.status())
                return
            if method == "POST" and parts in (["heart", "connect"], ["heart", "disconnect"]):
                self.body()
                if parts[-1] == "connect":
                    result = study.heart.start()
                else:
                    study.heart.stop()
                    result = study.heart.status()
                self.reply(200, result)
                return
            if method == "POST" and parts == ["sessions"]:
                self.reply(201, study.create(self.body()))
                return
            if len(parts) < 2 or parts[0] != "sessions" or not re.fullmatch(r"[0-9a-f]{32}", parts[1]):
                self.reply(404, {"error": "Unknown study route"})
                return
            session_id = parts[1]
            if method == "GET" and len(parts) == 2:
                self.reply(200, study.snapshot(session_id))
                return
            if method != "POST" or len(parts) != 3:
                self.reply(404, {"error": "Unknown study route"})
                return
            data, action = self.body(), parts[2]
            if action == "observations":
                result = study.observe(session_id, data)
            elif action == "checkins":
                result = study.checkin(session_id, data)
            elif action == "focus-events":
                result = study.focus_events(session_id, data)
            elif action == "context-help":
                result = study.context_help(session_id, data)
            elif action == "materials":
                result = study.update_material(session_id,data)
            elif action == "screen-help":
                result = study.screen_help(session_id, data)
            elif action == "assist":
                result = study.assist(session_id, data)
            elif action == "feedback":
                result = study.feedback(session_id, data)
            elif action == "pause":
                result = study.pause(session_id, data.get("paused"))
            elif action == "end":
                result = study.end(session_id)
            else:
                self.reply(404, {"error": "Unknown study action"})
                return
            self.reply(200, result)

        def body(self):
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked request bodies are not supported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("Invalid request body length")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Content-Type must be application/json")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Body must be a JSON object")
            return data

        def dispatch(self, method):
            try:
                if not self.authorized():
                    return
                parsed = urlsplit(self.path)
                parts = [x for x in parsed.path.split("/") if x]
                query = parse_qs(parsed.query)
                if method == "GET" and parts == ["health"]:
                    settings = ModelSettings.read()
                    self.reply(200, {"ok": True, "api_version": "0.4", "live_key_configured": bool(settings.api_key),
                                     "model": settings.public(), "study_model": TutorModel.read().public()})
                    return
                if parts and parts[0] == "study":
                    self.study_dispatch(method, parts[1:])
                    return
                if method == "POST" and parts == ["tasks"]:
                    session = service.create(self.body())
                    self.reply(202, session.snapshot())
                    return
                if len(parts) < 2 or parts[0] != "tasks":
                    self.reply(404, {"error": "Unknown route"})
                    return
                session = service.get(parts[1])
                if method == "GET" and len(parts) == 2:
                    self.reply(200, session.snapshot())
                    return
                route = "/".join(parts[2:])
                if method == "GET" and route == "events":
                    cursor = int(query.get("after", [self.headers.get("Last-Event-ID", "0")])[0])
                    if cursor < 0:
                        raise ValueError("Invalid event cursor")
                    if query.get("stream", ["0"])[0] != "1":
                        events = session.events.read(cursor, wait=min(20, max(0, float(query.get("wait", ["0"])[0]))))
                        self.reply(200, {"events": events, "cursor": events[-1]["seq"] if events else cursor})
                    else:
                        self.stream_events(session, cursor)
                    return
                if method == "GET" and len(parts) == 4 and parts[2] == "screens":
                    if not re.fullmatch(r"[0-9a-f]{32}\.png", parts[3]):
                        raise ValueError("Invalid screen id")
                    path = session.folder / "screens" / parts[3]
                    if not path.is_file():
                        self.reply(404, {"error": "Screen not found"})
                        return
                    raw = path.read_bytes()
                    self.send_response(200)
                    self.headers_for("image/png")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if method != "POST":
                    self.reply(404, {"error": "Unknown route"})
                    return
                data = self.body()
                if route == "messages":
                    was_waiting = session.status == "waiting_input"
                    session.chat(data.get("message"))
                    if was_waiting:
                        def resume():
                            previous = session.worker
                            if previous:
                                previous.join()
                            session.start()
                        import threading
                        threading.Thread(target=resume, daemon=True).start()
                elif route == "cancel":
                    session.cancel()
                elif route == "computer/results":
                    if session.task.mode != "live" or session.task.environment == "sandbox":
                        raise ValueError("This task uses its own isolated local host")
                    session.exchange.answer(data.get("request_id"), data.get("result"))
                elif route == "approvals":
                    session.approvals.answer(data.get("approval_id"), data.get("approved"))
                elif route == "reviews":
                    if session.status not in TERMINAL | {"waiting_input"}:
                        raise ValueError("Review a paused or finished plan")
                    session.learning.review(session, data.get("corrected_plan"), data.get("feedback", ""),
                                            data.get("consent_for_training", False))
                else:
                    self.reply(404, {"error": "Unknown route"})
                    return
                self.reply(200, session.snapshot())
            except ProviderError as exc:
                self.reply(502, {"error": str(exc)[:500]})
            except (ValueError, KeyError, TypeError) as exc:
                self.close_connection = True
                self.reply(400, {"error": str(exc)[:500]})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.close_connection = True
                self.reply(500, {"error": "Backend error; inspect local run state"})

        def stream_events(self, session, cursor):
            self.send_response(200)
            self.headers_for("text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            # Bounded stream: reconnect with the last received cursor.
            import time
            until = time.monotonic() + 50
            while time.monotonic() < until:
                events = session.events.read(cursor, wait=10)
                for event in events:
                    raw = f"id: {event['seq']}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    self.wfile.write(raw.encode())
                    cursor = event["seq"]
                if not events:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
                if session.status in TERMINAL and cursor >= len(session.events.items):
                    break

    return Handler


def serve(root, port=8765):
    token = os.getenv("LAST_HOUR_TOKEN", "")
    if len(token) < 24:
        raise ValueError("Set LAST_HOUR_TOKEN to a local bearer token of at least 24 characters")
    service = Service(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service, token, os.getenv("LAST_HOUR_ORIGIN")))
    server.daemon_threads = True
    print(f"AI backend listening on http://127.0.0.1:{port}; Ctrl+C to stop.")
    print("In-flight runs stop at process exit; run history remains on disk.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        for session in service.sessions.values():
            if session.status not in TERMINAL:
                session.cancel()
    finally:
        service.study.heart.stop()
        server.server_close()
