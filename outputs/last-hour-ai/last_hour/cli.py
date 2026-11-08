from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

from .engine import Service, TERMINAL
from .config import ModelSettings, load_env
from .policy import LearningStore
from .tutor_model import TutorModel


def demo_task(minutes=60):
    return {
        "mode": "rehearsal", "task_family": "assignment_submission",
        "goal": "가상 과제함에 내가 작성한 학습 계획을 저장하고 제출 접수증을 확인해줘.",
        "deadline": (datetime.now(timezone(timedelta(hours=9))) + timedelta(minutes=minutes)).isoformat(),
        "context": "이번 주 학습 계획\n월요일: 강의 복습 30분\n수요일: 연습문제 5개 풀기\n금요일: 오답과 배운 점 정리\n\n직접 작성한 테스트용 계획입니다.",
        "allowed_apps": ["assignment-demo"], "allowed_domains": [],
        "allowed_effects": ["read", "edit", "submit"], "reserve_seconds": 300,
        "success_criteria": [
            {"id": "draft_saved", "description": "저장된 초안이 사용자가 제공한 내용과 일치"},
            {"id": "submission_receipt", "description": "해당 과제의 제출 접수증이 표시됨"},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Study Signal backend — local study companion")
    parser.add_argument("--data", default=None)
    parser.add_argument("--env-file", default=None, help="Dotenv file; defaults to current/project .env")
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    demo = commands.add_parser("demo")
    demo.add_argument("--approve-demo-submission", action="store_true",
                      help="Approve only the fictional local demo submission")
    commands.add_parser("sample-task")
    commands.add_parser("check-config", help="Show model settings and key presence, without API calls")
    commands.add_parser("check-model", help="Make a small paid model connectivity request; no computer actions")
    relay = commands.add_parser("heart-relay", help="Run a standalone Watch heart-rate collector relay")
    relay.add_argument("--host", default="127.0.0.1")
    relay.add_argument("--port", type=int, default=8787)
    export = commands.add_parser("export")
    export.add_argument("--output", required=True)
    study_export = commands.add_parser("study-export", help="Export only consented and reviewed tutor examples")
    study_export.add_argument("--output", required=True)
    args = parser.parse_args()
    env_path = load_env(args.env_file)
    data_root = args.data or os.getenv("LAST_HOUR_DATA", "./data")
    if args.command == "serve":
        from .api import serve
        serve(data_root, args.port)
    elif args.command == "heart-relay":
        from .heart_feed import serve_relay
        serve_relay(args.host, args.port)
    elif args.command == "sample-task":
        print(json.dumps(demo_task(), ensure_ascii=False, indent=2))
    elif args.command == "export":
        print(json.dumps(LearningStore(Path(data_root)).export(Path(args.output)), ensure_ascii=False, indent=2))
    elif args.command == "study-export":
        from .study import StudyService
        print(json.dumps(StudyService(data_root).export(args.output), ensure_ascii=False, indent=2))
    elif args.command == "check-config":
        settings = ModelSettings.read()
        print(json.dumps({**settings.public(), "env_file": str(env_path.resolve()),
                          "local_token_configured": len(os.getenv("LAST_HOUR_TOKEN", "")) >= 24,
                          "study_model": TutorModel.read().public()}, ensure_ascii=False, indent=2))
    elif args.command == "check-model":
        from .openrouter import OpenRouterClient, assistant_message, parse_object
        settings = ModelSettings.read()
        settings.require_key()
        if settings.provider != "openrouter":
            raise ValueError("check-model currently supports AI_PROVIDER=openrouter")
        async def check():
            for model in dict.fromkeys((settings.policy_model, settings.computer_model)):
                response = await OpenRouterClient(settings).complete(
                    model=model, messages=[{"role": "user", "content": 'Return only JSON: {"ok": true}'}],
                    max_tokens=2048, response_format={"type": "json_object"})
                if parse_object(assistant_message(response).get("content")).get("ok") is not True:
                    raise ValueError("Model connectivity check returned unexpected output")
                print(json.dumps({"model": model, "connected": True, "computer_actions": 0}))
        asyncio.run(check())
    else:
        service = Service(data_root)
        session = service.create(demo_task())
        print("Deterministic rehearsal in a real isolated browser. No model inference or external submission.")
        cursor = 0
        while True:
            for event in session.events.read(cursor, wait=0.2):
                cursor = event["seq"]
                if event["type"] in {"task.status", "chat.assistant", "computer.action"}:
                    print(event["type"], json.dumps(event["data"], ensure_ascii=False))
                elif event["type"] == "approval.required":
                    if args.approve_demo_submission:
                        session.approvals.answer(event["data"]["id"], True)
                    else:
                        approved = input("가상 과제함에 제출할까요? [y/N] ").strip().lower() == "y"
                        session.approvals.answer(event["data"]["id"], approved)
            if session.status in TERMINAL:
                session.worker.join(timeout=6)
                print("Run folder:", session.folder)
                print("Result:", session.status)
                if session.status != "completed":
                    raise SystemExit(1)
                break


if __name__ == "__main__":
    main()
