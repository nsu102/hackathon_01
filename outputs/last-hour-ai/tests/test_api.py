import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from last_hour.api import make_handler
from last_hour.cli import demo_task
from last_hour.engine import Service, Session
from last_hour.models import Task


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(self.tmp.name)
        self.token = "test-token-only-123456789012345"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.service, self.token, "http://localhost:3000"))
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, data=None, *, auth=True, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        if origin:
            headers["Origin"] = origin
        conn.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse()
        result = (response.status, json.loads(response.read()))
        conn.close()
        return result

    def test_local_auth_and_origin_are_enforced(self):
        self.assertEqual(self.request("GET", "/health", auth=False)[0], 401)
        self.assertEqual(self.request("GET", "/health", origin="https://unrelated.test")[0], 403)
        self.assertEqual(self.request("GET", "/health", origin="http://localhost:3000")[0], 200)

    def test_missing_fields_are_rejected_before_dispatch(self):
        self.assertEqual(self.request("POST", "/tasks", {"goal": "Submit"})[0], 400)
        self.assertEqual(len(self.service.sessions), 0)

    def test_task_events_messages_and_cancel_contract(self):
        session = Session(Task.parse(demo_task()), Path(self.tmp.name))
        self.service.sessions[session.id] = session
        status, snapshot = self.request("GET", "/tasks/" + session.id)
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["status"], "created")
        status, _ = self.request("POST", f"/tasks/{session.id}/messages", {"message": "요약부터 해줘"})
        self.assertEqual(status, 200)
        _, events = self.request("GET", f"/tasks/{session.id}/events?after=1")
        self.assertEqual(events["events"][0]["type"], "chat.user")
        self.assertEqual(self.request("POST", f"/tasks/{session.id}/cancel", {})[0], 200)
        self.assertEqual(session.status, "cancelled")
        self.assertEqual(self.request("POST", f"/tasks/{session.id}/messages", {"message": "continue"})[0], 400)

    def test_study_http_session_assistance_and_sensor_contract(self):
        status, value = self.request("POST", "/study/sessions", {"goal": "확률", "material": "기준 사건", "ai_enabled": False})
        self.assertEqual(status, 201)
        prefix = "/study/sessions/" + value["id"]
        self.assertEqual(self.request("POST", prefix + "/observations", {"frames": []})[0], 400)
        event = {"from":"away_pending","to":"away","reason":"offscreen","at_ms":10000,"duration_ms":8000,"correction":None}
        self.assertEqual(self.request("POST", prefix + "/focus-events", event)[0], 200)
        self.assertEqual(self.request("POST", prefix + "/focus-events", {**event,"raw_gaze":[]})[0], 400)
        self.assertEqual(self.request("POST", prefix + "/context-help", {"consent":False})[0], 400)
        status, answer = self.request("POST", prefix + "/assist", {"mode": "hint", "message": ""})
        self.assertEqual(status, 200)
        self.assertEqual(answer["source"], "demo")
        self.assertEqual(self.request("POST", prefix + "/pause", {"paused": True})[1]["status"], "paused")
        self.assertEqual(self.request("POST", prefix + "/end", {})[1]["status"], "ended")
        self.assertEqual(self.request("POST", prefix + "/assist", {"mode": "hint", "message": ""})[0], 400)
        self.assertIsNone(self.request("GET", "/study/heart")[1]["bpm"])

    def test_screen_route_does_not_accept_arbitrary_paths(self):
        session = Session(Task.parse(demo_task()), Path(self.tmp.name))
        self.service.sessions[session.id] = session
        self.assertEqual(self.request("GET", f"/tasks/{session.id}/screens/task.json")[0], 400)


if __name__ == "__main__":
    unittest.main()
