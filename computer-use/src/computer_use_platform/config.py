from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass
class RuntimeConfig:
    ai_provider: str
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_timeout: int
    headless: bool
    auth_state_path: str
    auth_url: str

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key and self.ai_model)

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        load_dotenv_file()

        def first(*keys: str, default: str = "") -> str:
            for key in keys:
                value = os.getenv(key)
                if value:
                    return value
            return default

        headless_raw = first("COMPUTER_USE_HEADLESS", default="true").lower()
        return cls(
            ai_provider=first("COMPUTER_USE_AI_PROVIDER", default="openai_compatible"),
            ai_api_key=first("COMPUTER_USE_AI_API_KEY", "OPENAI_API_KEY"),
            ai_base_url=first("COMPUTER_USE_AI_BASE_URL", "OPENAI_BASE_URL", default="https://api.openai.com/v1"),
            ai_model=first("COMPUTER_USE_AI_MODEL", "OPENAI_MODEL", default="gpt-5.4-mini"),
            ai_timeout=int(first("COMPUTER_USE_AI_TIMEOUT", default="60")),
            headless=headless_raw not in {"0", "false", "no"},
            auth_state_path=first("COMPUTER_USE_AUTH_STATE_PATH", default="auth/storage_state.json"),
            auth_url=first("COMPUTER_USE_AUTH_URL", default="https://beta-5.bydtms.com/zh/login"),
        )
