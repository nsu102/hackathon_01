"""Local settings. Reading a .env never executes shell code or prints its values."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shlex
from urllib.parse import urlsplit


DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def default_env_path() -> Path:
    local = Path.cwd() / ".env"
    return local if local.is_file() else PROJECT_ROOT / ".env"


def load_env(path: Path | str | None = None) -> Path:
    """Load simple dotenv assignments. Existing exported values take precedence.

    Supports export, quotes and comments, without expansion, substitutions or eval.
    Parse the entire file before changing the environment so errors are atomic.
    """
    source = Path(path) if path is not None else default_env_path()
    if not source.is_file():
        if path is not None:
            raise ValueError("The specified .env file does not exist")
        return source
    values = {}
    for number, raw in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid .env assignment at line {number}")
        try:
            lexer = shlex.shlex(value, posix=True)
            lexer.whitespace_split = True
            lexer.commenters = "#"
            pieces = list(lexer)
        except ValueError as exc:
            raise ValueError(f"Invalid .env quotes at line {number}") from exc
        if len(pieces) > 1:
            raise ValueError(f"Quote .env values containing spaces (line {number})")
        values[name] = pieces[0] if pieces else ""
    for name, value in values.items():
        os.environ.setdefault(name, value)
    return source


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    api_key: str = field(repr=False)
    policy_model: str
    computer_model: str
    base_url: str
    reasoning_effort: str = "low"

    @classmethod
    def read(cls):
        provider = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
        if provider == "openrouter":
            model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
            settings = cls(
                provider=provider, api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
                policy_model=os.getenv("OPENROUTER_POLICY_MODEL", "").strip() or model,
                computer_model=os.getenv("OPENROUTER_COMPUTER_MODEL", "").strip() or model,
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
                reasoning_effort=os.getenv("OPENROUTER_REASONING_EFFORT", "low").strip(),
            )
            parsed = urlsplit(settings.base_url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
                raise ValueError("OPENROUTER_BASE_URL must be an HTTPS API base URL")
            if settings.reasoning_effort not in {"low", "medium", "high"}:
                raise ValueError("OPENROUTER_REASONING_EFFORT must be low, medium or high")
        elif provider == "openai":
            settings = cls(provider, os.getenv("OPENAI_API_KEY", "").strip(),
                           os.getenv("OPENAI_POLICY_MODEL", "gpt-6.1-sol"),
                           os.getenv("OPENAI_COMPUTER_MODEL", "gpt-6.1-sol"),
                           "https://api.openai.com/v1")
        else:
            raise ValueError("AI_PROVIDER must be openrouter or openai")
        for model in (settings.policy_model, settings.computer_model):
            if not model or len(model) > 255 or any(c.isspace() for c in model):
                raise ValueError("Model ids must be nonempty slugs without whitespace")
        return settings

    def require_key(self):
        variable = "OPENROUTER_API_KEY" if self.provider == "openrouter" else "OPENAI_API_KEY"
        if not self.api_key or self.api_key in {"your-api-key", "your-project-api-key", "replace-me"}:
            raise ValueError(f"Fill {variable} in .env, then restart the backend")

    def public(self):
        return {"provider": self.provider, "policy_model": self.policy_model,
                "computer_model": self.computer_model, "key_configured": bool(self.api_key),
                "reasoning_effort": self.reasoning_effort}
