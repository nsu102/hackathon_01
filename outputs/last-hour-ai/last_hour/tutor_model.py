"""Selectable hosted or fine-tuned tutor inference, using Chat Completions."""
import asyncio
from dataclasses import dataclass, field
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .config import ModelSettings
from .openrouter import OpenRouterClient, NoRedirect, ProviderError


@dataclass
class TutorModel:
    provider: str
    model: str
    endpoint: str
    api_key: str = field(repr=False)
    hosted_settings: object = field(default=None, repr=False)

    @classmethod
    def read(cls):
        provider = os.getenv("STUDY_MODEL_PROVIDER", "openrouter")
        if provider == "openrouter":
            settings = ModelSettings.read()
            return cls(provider, os.getenv("STUDY_MODEL_ID", "").strip() or settings.policy_model,
                       settings.base_url, settings.api_key, settings)
        if provider != "compatible":
            raise ValueError("STUDY_MODEL_PROVIDER must be openrouter or compatible")
        return cls(provider, os.getenv("STUDY_MODEL_ID", "study-tutor").strip() or "study-tutor",
                   os.getenv("STUDY_MODEL_ENDPOINT", "http://127.0.0.1:8001/v1").rstrip("/"),
                   os.getenv("STUDY_MODEL_API_KEY", "").strip())

    def require(self):
        if self.provider == "openrouter":
            self.hosted_settings.require_key()
            return
        url = urlsplit(self.endpoint)
        local = url.hostname in {"127.0.0.1", "localhost"}
        if (not url.hostname or url.username or url.password or url.query or url.fragment
            or not (url.scheme == "https" or url.scheme == "http" and local)):
            raise ValueError("모델 서버는 HTTPS 또는 로컬 SSH 터널 주소를 사용해주세요.")
        if not local and not self.api_key:
            raise ValueError("원격 모델 서버의 API 키를 설정해주세요.")

    def public(self):
        return {"provider": self.provider, "model": self.model,
                "configured": bool(self.api_key) if self.provider == "openrouter" else bool(self.endpoint)}

    def _send(self, messages):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        body = {"model": self.model, "messages": messages, "stream": False,
                "max_tokens": 2048, "response_format": {"type": "json_object"}}
        request = Request(self.endpoint + "/chat/completions", data=json.dumps(body, ensure_ascii=False).encode(), headers=headers)
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(4_000_001)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise ProviderError(f"모델 서버 HTTP {code}: 모델 이름·인증·서빙 상태를 확인해주세요.") from None
        except (URLError, TimeoutError, OSError):
            raise ProviderError("GPU 모델 서버 연결 실패: SSH 터널과 서빙 프로세스를 확인해주세요.") from None
        if len(raw) > 4_000_000:
            raise ProviderError("모델 응답이 너무 커요.")
        try:
            result = json.loads(raw)
        except ValueError:
            raise ProviderError("모델 서버의 JSON 응답을 확인하지 못했어요.") from None
        if not isinstance(result, dict) or result.get("error"):
            raise ProviderError("모델 서버가 오류를 반환했어요.")
        return result

    async def complete(self, messages):
        self.require()
        if self.provider == "openrouter":
            return await OpenRouterClient(self.hosted_settings).complete(model=self.model, messages=messages,
                response_format={"type": "json_object"}, max_tokens=4096)
        return await asyncio.to_thread(self._send, messages)
