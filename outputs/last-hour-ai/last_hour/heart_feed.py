"""Watch -> collector server -> study app. No direct Watch pairing or workouts."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .openrouter import NoRedirect


def parse_sample(value, now):
    if not isinstance(value, dict) or set(value) != {"bpm", "timestamp", "source", "sample_id"}:
        raise ValueError("Expected bpm, timestamp, source and sample_id")
    bpm = value["bpm"]
    if type(bpm) not in (int, float) or not math.isfinite(bpm) or not 20 <= bpm <= 250:
        raise ValueError("Invalid heart rate")
    try:
        stamp = datetime.fromisoformat(value["timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError()
        at = stamp.timestamp()
    except (ValueError, TypeError, AttributeError):
        raise ValueError("An ISO 8601 timestamp with timezone is required") from None
    if not -10 <= now - at <= 60:
        raise ValueError("Stale or future sample")
    if value["source"] not in {"apple_watch", "demo"}:
        raise ValueError("Unknown heart rate source")
    if not isinstance(value["sample_id"], str) or not 1 <= len(value["sample_id"]) <= 128:
        raise ValueError("Invalid sample id")
    return {**value, "bpm": float(bpm)}, at


class HeartRateFeed:
    def __init__(self, clock=time.time, fetch=None):
        self.clock, self.fetch = clock, fetch
        self.lock = threading.RLock()
        self.samples = deque(maxlen=120)
        self.thread = None
        self.stop_event = threading.Event()
        self.message = "심박 서버 미연결"
        self.running = False

    def accept(self, value):
        sample, at = parse_sample(value, self.clock())
        with self.lock:
            if self.samples and sample["source"] != self.samples[-1]["source"]:
                self.samples.clear()  # Never mix demo data into a real baseline.
            if any(s["sample_id"] == sample["sample_id"] for s in self.samples):
                return False
            if self.samples and at < self.samples[-1]["at"]:
                return False
            self.samples.append({**sample, "at": at})
            self.message = "데모 서버 신호" if sample["source"] == "demo" else "Apple Watch · 서버 수신"
            return True

    def status(self):
        with self.lock:
            sample = self.samples[-1] if self.samples else None
            age = self.clock() - sample["at"] if sample else None
            fresh = bool(sample and age <= 20 and self.running)
            recent = sorted(s["bpm"] for s in self.samples if self.clock() - s["at"] <= 180)
            baseline = recent[len(recent) // 2] if len(recent) >= 15 and fresh else None
            return {"source": sample["source"] if sample else "none", "connected": fresh,
                    "bpm": round(sample["bpm"]) if fresh else None,
                    "age_seconds": round(max(0, age), 1) if age is not None else None,
                    "baseline_bpm": round(baseline, 1) if baseline is not None else None,
                    "sample_count": len(recent), "reading": self.running,
                    "message": self.message if fresh or not sample else "심박 데이터가 오래됐어요"}

    def _read(self, url, token):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=5) as response:
            raw = response.read(4097)
        if len(raw) > 4096:
            raise ValueError("Heart response too large")
        return json.loads(raw)

    def start(self):
        url = os.getenv("STUDY_HEART_URL", "").strip()
        token = os.getenv("STUDY_HEART_TOKEN", "").strip()
        parsed = urlsplit(url)
        if not url:
            raise ValueError(".env의 STUDY_HEART_URL에 심박 서버의 최신값 주소를 넣어주세요.")
        if (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("심박 서버는 HTTPS 주소를 사용해주세요. 로컬 테스트는 127.0.0.1 HTTP를 허용해요.")
        if not parsed.hostname:
            raise ValueError("심박 서버 주소를 확인해주세요.")
        with self.lock:
            if self.running:
                return self.status()
            self.running = True
            self.stop_event = threading.Event()
            stop_event = self.stop_event
            self.message = "심박 서버 응답 대기"
            self.samples.clear()
            def poll():
                while not stop_event.is_set():
                    try:
                        value = (self.fetch or self._read)(url, token)
                        if stop_event.is_set():
                            return
                        if not (isinstance(value, dict) and value.get("status") == "waiting"):
                            self.accept(value)
                    except Exception:
                        with self.lock:
                            self.message = "심박 서버 연결·인증·데이터 형식을 확인해주세요"
                    stop_event.wait(2)
            self.thread = threading.Thread(target=poll, daemon=True)
            self.thread.start()
            return self.status()

    def stop(self):
        with self.lock:
            self.running = False
            self.stop_event.set()
            self.message = "심박 서버 미연결"
            self.samples.clear()


class HeartRelay:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.latest = None
        self.at = 0
        self.seen = deque(maxlen=256)

    def push(self, value):
        sample, at = parse_sample(value, self.clock())
        with self.lock:
            if sample["sample_id"] in self.seen:
                return {"accepted": False, "reason": "duplicate"}
            if at < self.at:
                raise ValueError("Out-of-order sample")
            self.latest, self.at = sample, at
            self.seen.append(sample["sample_id"])
            return {"accepted": True}

    def read(self):
        with self.lock:
            return dict(self.latest) if self.latest else {"status": "waiting"}


def relay_handler(relay, write_token, read_token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, data):
            raw = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authenticated(self, expected):
            supplied = self.headers.get("Authorization", "")
            return not self.headers.get("Origin") and hmac.compare_digest(supplied, "Bearer " + expected)

        def do_GET(self):
            if not self.authenticated(read_token):
                self.respond(401, {"error": "Read token required"})
            elif self.path != "/heart-rate/latest":
                self.respond(404, {"error": "Unknown route"})
            else:
                self.respond(200, relay.read())

        def do_POST(self):
            if not self.authenticated(write_token):
                self.respond(401, {"error": "Ingest token required"})
                return
            if self.path != "/heart-rate":
                self.respond(404, {"error": "Unknown route"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (self.headers.get("Transfer-Encoding") or not 0 < length <= 2048
                    or self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                    raise ValueError()
                self.respond(200, relay.push(json.loads(self.rfile.read(length))))
            except (ValueError, TypeError):
                self.respond(400, {"error": "Invalid, stale or out-of-order sample"})
    return Handler


def serve_relay(host="127.0.0.1", port=8787):
    write_token = os.getenv("HEART_INGEST_TOKEN", "")
    read_token = os.getenv("HEART_READ_TOKEN", "")
    if min(len(write_token), len(read_token)) < 24 or hmac.compare_digest(write_token, read_token):
        raise ValueError("Set distinct HEART_INGEST_TOKEN and HEART_READ_TOKEN values of at least 24 characters")
    server = ThreadingHTTPServer((host, port), relay_handler(HeartRelay(), write_token, read_token))
    server.daemon_threads = True
    print(f"Heart relay listening on {host}:{port}. Use an HTTPS reverse proxy for remote access.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
