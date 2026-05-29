from __future__ import annotations

from pathlib import Path
from typing import Any, List, Set, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central runtime configuration for Atrioly · Wanatring.

    Values are loaded from environment variables and `.env`.
    Keep real secrets only in `.env`; never commit them.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Credentials
    TELEGRAM_BOT_TOKEN: str = ""
    AI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_COMPATIBLE_API_KEY: str | None = None

    # AI Provider Router
    AI_PROVIDER: str = "openai"  # openai | deepseek | anthropic | openai_compatible
    AI_PROVIDER_FALLBACKS: str | None = None
    DEFAULT_MODEL: str = "gpt-4o-mini"
    RADAR_MODEL: str | None = None
    PRIVATE_MODEL: str | None = None
    TASK_MODEL: str | None = None
    CHAT_MODEL: str | None = None
    VISION_MODEL: str = "gpt-4o"
    AI_VISION_MODEL: str | None = None  # Backward-compatible alias

    # Provider endpoints and models
    AI_BASE_URL: str | None = None
    OPENAI_BASE_URL: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-latest"
    OPENAI_COMPATIBLE_BASE_URL: str | None = None
    OPENAI_COMPATIBLE_MODEL: str | None = None

    # AI Runtime
    MAX_MESSAGE_LENGTH: int = 1200
    AI_REQUEST_TIMEOUT_SECONDS: float = 30.0
    AI_PROVIDER_CONNECT_TIMEOUT_SECONDS: float = 5.0
    AI_RETRY_TIMES: int = 2
    AI_PROVIDER_RETRY_TIMES: int = 1
    AI_FAILOVER_FAST_ON_NETWORK_ERROR: bool = True
    AI_TEMPERATURE: float = 0.2
    AI_CACHE_TTL_SECONDS: int = 300

    # Access Control & Routing
    OWNER_IDS: Set[int] = Field(default_factory=set)
    FORWARD_TO: List[int] = Field(default_factory=list)
    ADMIN_ONLY_AI_TEST: bool = True

    # Feature Flags
    ENABLE_AUTO_BAN: bool = True
    ENABLE_DAILY_REPORT: bool = False
    ENABLE_SENDER_PROFILE_LINK: bool = True
    ENABLE_AI_FILTER: bool = True
    ENABLE_HEURISTIC_FILTER: bool = True

    # Paths
    DATA_DIR: str = "/app/data"
    BLACKLIST_DB_FILE: str = "blacklist.json"
    MEMBERSHIP_DB_FILE: str = "memberships.json"
    STATE_DB_FILE: str = "state.json"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_AI_RESULT: bool = True
    LOG_FORWARD_ACTIONS: bool = True
    LOG_MODERATION_ACTIONS: bool = True

    # Time & Schedule
    DEFAULT_TIMEZONE: str = "Asia/Shanghai"
    DAILY_REPORT_TIME: str = "22:30"
    WEEKLY_REPORT_DAY: str = "SUN"
    WEEKLY_REPORT_TIME: str = "22:45"

    # Moderation
    MAX_STRIKES: int = 3
    WARNING_EXPIRE_DAYS: int = 30
    MIN_TEXT_LENGTH_FOR_AI: int = 5

    # Radar
    RADAR_RECENT_HOURS: int = 24
    MIN_CONFIDENCE_TO_FORWARD: float = 0.65
    HIGH_RISK_THRESHOLD: int = 75

    @field_validator(
        "AI_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
        "RADAR_MODEL",
        "PRIVATE_MODEL",
        "TASK_MODEL",
        "CHAT_MODEL",
        "AI_VISION_MODEL",
        "AI_BASE_URL",
        "OPENAI_BASE_URL",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_MODEL",
        "AI_PROVIDER_FALLBACKS",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("OWNER_IDS", mode="before")
    @classmethod
    def parse_owner_ids(cls, value: Any) -> Set[int]:
        return set(cls._parse_id_collection(value))

    @field_validator("FORWARD_TO", mode="before")
    @classmethod
    def parse_forward_to(cls, value: Any) -> List[int]:
        return cls._parse_id_collection(value)

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: Any) -> str:
        level = str(value or "INFO").strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        return level if level in allowed else "INFO"

    @field_validator("AI_PROVIDER", mode="before")
    @classmethod
    def normalize_ai_provider(cls, value: Any) -> str:
        provider = str(value or "openai").strip().lower().replace("-", "_")
        allowed = {"openai", "deepseek", "anthropic", "openai_compatible"}
        return provider if provider in allowed else "openai"

    @field_validator("DEFAULT_MODEL", mode="before")
    @classmethod
    def normalize_default_model(cls, value: Any) -> str:
        model = str(value or "gpt-4o-mini").strip()
        return model or "gpt-4o-mini"

    @field_validator("VISION_MODEL", mode="before")
    @classmethod
    def normalize_vision_model(cls, value: Any) -> str:
        model = str(value or "gpt-4o").strip()
        return model or "gpt-4o"

    @field_validator("DEEPSEEK_BASE_URL", mode="before")
    @classmethod
    def normalize_deepseek_base_url(cls, value: Any) -> str:
        base_url = str(value or "https://api.deepseek.com/v1").strip().rstrip("/")
        return base_url or "https://api.deepseek.com/v1"

    @field_validator("DEEPSEEK_MODEL", mode="before")
    @classmethod
    def normalize_deepseek_model(cls, value: Any) -> str:
        model = str(value or "deepseek-v4-flash").strip()
        return model or "deepseek-v4-flash"

    @field_validator("ANTHROPIC_MODEL", mode="before")
    @classmethod
    def normalize_anthropic_model(cls, value: Any) -> str:
        model = str(value or "claude-3-5-haiku-latest").strip()
        return model or "claude-3-5-haiku-latest"

    @field_validator("MAX_MESSAGE_LENGTH")
    @classmethod
    def validate_max_message_length(cls, value: int) -> int:
        return max(100, min(value, 12000))

    @field_validator("AI_REQUEST_TIMEOUT_SECONDS")
    @classmethod
    def validate_ai_timeout(cls, value: float) -> float:
        return max(5.0, min(float(value), 180.0))

    @field_validator("AI_PROVIDER_CONNECT_TIMEOUT_SECONDS")
    @classmethod
    def validate_ai_provider_connect_timeout(cls, value: float) -> float:
        return max(1.0, min(float(value), 30.0))

    @field_validator("AI_RETRY_TIMES")
    @classmethod
    def validate_ai_retry_times(cls, value: int) -> int:
        return max(0, min(value, 5))

    @field_validator("AI_PROVIDER_RETRY_TIMES")
    @classmethod
    def validate_ai_provider_retry_times(cls, value: int) -> int:
        return max(0, min(value, 3))

    @field_validator("AI_TEMPERATURE")
    @classmethod
    def validate_ai_temperature(cls, value: float) -> float:
        return max(0.0, min(value, 2.0))

    @field_validator("AI_CACHE_TTL_SECONDS")
    @classmethod
    def validate_cache_ttl(cls, value: int) -> int:
        return max(0, min(value, 86400))

    @field_validator("MIN_CONFIDENCE_TO_FORWARD")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        return max(0.0, min(value, 1.0))

    @field_validator("HIGH_RISK_THRESHOLD")
    @classmethod
    def validate_risk_threshold(cls, value: int) -> int:
        return max(0, min(value, 100))

    @staticmethod
    def _parse_id_collection(value: Union[str, int, list[Any], set[Any], tuple[Any], None]) -> List[int]:
        """Parse Telegram ID collections from env-friendly formats."""
        if value is None:
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            raw = raw.replace("[", "").replace("]", "")
            parts = [part.strip() for part in raw.split(",") if part.strip()]
        elif isinstance(value, (list, set, tuple)):
            parts = list(value)
        else:
            return []

        parsed: List[int] = []
        for item in parts:
            try:
                parsed.append(int(str(item).strip()))
            except (TypeError, ValueError):
                continue
        return parsed

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR)

    @property
    def blacklist_path(self) -> Path:
        return self.data_path / self.BLACKLIST_DB_FILE

    @property
    def membership_path(self) -> Path:
        return self.data_path / self.MEMBERSHIP_DB_FILE

    @property
    def state_path(self) -> Path:
        return self.data_path / self.STATE_DB_FILE

    @property
    def effective_openai_key(self) -> str | None:
        return self.OPENAI_API_KEY or self.AI_API_KEY

    @property
    def effective_deepseek_key(self) -> str | None:
        return self.DEEPSEEK_API_KEY or self.AI_API_KEY

    @property
    def effective_anthropic_key(self) -> str | None:
        return self.ANTHROPIC_API_KEY or self.AI_API_KEY

    @property
    def effective_openai_compatible_key(self) -> str | None:
        return self.OPENAI_COMPATIBLE_API_KEY or self.AI_API_KEY

    @property
    def effective_vision_model(self) -> str:
        return self.AI_VISION_MODEL or self.VISION_MODEL

    @property
    def effective_default_model(self) -> str:
        if self.AI_PROVIDER == "deepseek":
            return self.DEEPSEEK_MODEL
        if self.AI_PROVIDER == "anthropic":
            return self.ANTHROPIC_MODEL
        if self.AI_PROVIDER == "openai_compatible" and self.OPENAI_COMPATIBLE_MODEL:
            return self.OPENAI_COMPATIBLE_MODEL
        return self.DEFAULT_MODEL

    def get_model_for_task(self, task: str, provider: str | None = None) -> str:
        task_name = str(task or "").strip().lower()
        provider_name = self._normalize_provider_name(provider or self.AI_PROVIDER)

        if provider is None:
            if task_name == "radar" and self.RADAR_MODEL:
                return self.RADAR_MODEL
            if task_name == "private" and self.PRIVATE_MODEL:
                return self.PRIVATE_MODEL
            if task_name == "task" and self.TASK_MODEL:
                return self.TASK_MODEL
            if task_name == "chat" and self.CHAT_MODEL:
                return self.CHAT_MODEL
            if task_name == "vision":
                return self.effective_vision_model
            return self.effective_default_model

        # Provider-specific defaults for failover/runtime override execution.
        if task_name == "vision":
            if provider_name == "deepseek":
                return self.DEEPSEEK_MODEL
            if provider_name == "anthropic":
                return self.ANTHROPIC_MODEL
            if provider_name == "openai_compatible":
                return self.OPENAI_COMPATIBLE_MODEL or self.DEFAULT_MODEL
            return self.effective_vision_model

        if provider_name == "deepseek":
            return self.DEEPSEEK_MODEL
        if provider_name == "anthropic":
            return self.ANTHROPIC_MODEL
        if provider_name == "openai_compatible":
            return self.OPENAI_COMPATIBLE_MODEL or self.DEFAULT_MODEL

        # OpenAI provider-specific path keeps task overrides.
        if task_name == "radar" and self.RADAR_MODEL:
            return self.RADAR_MODEL
        if task_name == "private" and self.PRIVATE_MODEL:
            return self.PRIVATE_MODEL
        if task_name == "task" and self.TASK_MODEL:
            return self.TASK_MODEL
        if task_name == "chat" and self.CHAT_MODEL:
            return self.CHAT_MODEL
        return self.DEFAULT_MODEL

    def get_api_key_for_provider(self, provider: str | None = None) -> str | None:
        provider_name = (provider or self.AI_PROVIDER or "openai").strip().lower().replace("-", "_")
        if provider_name == "deepseek":
            return self.effective_deepseek_key
        if provider_name == "anthropic":
            return self.effective_anthropic_key
        if provider_name == "openai_compatible":
            return self.effective_openai_compatible_key
        return self.effective_openai_key

    def get_base_url_for_provider(self, provider: str | None = None) -> str | None:
        provider_name = (provider or self.AI_PROVIDER or "openai").strip().lower().replace("-", "_")
        if provider_name == "deepseek":
            return self.DEEPSEEK_BASE_URL
        if provider_name == "openai_compatible":
            return self.OPENAI_COMPATIBLE_BASE_URL or self.AI_BASE_URL
        if provider_name == "openai":
            return self.OPENAI_BASE_URL or self.AI_BASE_URL
        return None

    @staticmethod
    def _normalize_provider_name(provider: str | None) -> str:
        provider_name = str(provider or "openai").strip().lower().replace("-", "_")
        allowed = {"openai", "deepseek", "anthropic", "openai_compatible"}
        return provider_name if provider_name in allowed else "openai"

    def is_provider_ready(self, provider: str) -> bool:
        provider_name = self._normalize_provider_name(provider)
        api_key = self.get_api_key_for_provider(provider_name)
        if not api_key:
            return False

        if provider_name == "openai_compatible":
            if not (self.OPENAI_COMPATIBLE_BASE_URL or self.AI_BASE_URL):
                return False
            if not (self.OPENAI_COMPATIBLE_MODEL or self.DEFAULT_MODEL):
                return False
            return True

        if provider_name == "openai":
            return bool(self.effective_openai_key)
        if provider_name == "deepseek":
            return bool(self.effective_deepseek_key)
        if provider_name == "anthropic":
            return bool(self.effective_anthropic_key)

        return False

    def get_default_model_for_provider(self, provider: str) -> str:
        provider_name = self._normalize_provider_name(provider)
        if provider_name == "deepseek":
            return self.DEEPSEEK_MODEL
        if provider_name == "anthropic":
            return self.ANTHROPIC_MODEL
        if provider_name == "openai_compatible":
            return self.OPENAI_COMPATIBLE_MODEL or self.DEFAULT_MODEL
        return self.DEFAULT_MODEL

    def get_ready_ai_providers(self) -> List[str]:
        ordered = ["openai", "deepseek", "anthropic", "openai_compatible"]
        return [provider for provider in ordered if self.is_provider_ready(provider)]

    def get_ai_provider_fallback_chain(self, primary: str | None = None) -> List[str]:
        effective_primary = self._normalize_provider_name(primary or self.AI_PROVIDER)
        configured_raw = self.AI_PROVIDER_FALLBACKS
        configured: List[str] = []
        if configured_raw:
            configured = [
                self._normalize_provider_name(item)
                for item in configured_raw.split(",")
                if str(item).strip()
            ]

        chain: List[str] = []
        seen: set[str] = set()

        for provider in [effective_primary, *configured] if configured else [effective_primary, "openai", "deepseek", "anthropic", "openai_compatible"]:
            p = self._normalize_provider_name(provider)
            if p in seen:
                continue
            seen.add(p)
            if self.is_provider_ready(p):
                chain.append(p)

        return chain

    def public_ai_failover_summary(self) -> dict[str, Any]:
        return {
            "default_provider": self.AI_PROVIDER,
            "configured_fallbacks": self.AI_PROVIDER_FALLBACKS,
            "ready_providers": self.get_ready_ai_providers(),
            "fallback_chain": self.get_ai_provider_fallback_chain(),
        }

    def active_ai_key_configured(self) -> bool:
        return bool(self.get_api_key_for_provider())

    def active_ai_provider_ready(self) -> bool:
        if not self.active_ai_key_configured():
            return False
        if self.AI_PROVIDER == "openai_compatible" and not self.OPENAI_COMPATIBLE_BASE_URL:
            return False
        return True

    def public_ai_summary(self) -> dict[str, Any]:
        return {
            "provider": self.AI_PROVIDER,
            "model": self.effective_default_model,
            "radar_model": self.get_model_for_task("radar"),
            "private_model": self.get_model_for_task("private"),
            "task_model": self.get_model_for_task("task"),
            "chat_model": self.get_model_for_task("chat"),
            "vision_model": self.get_model_for_task("vision"),
            "base_url_configured": bool(self.get_base_url_for_provider()),
            "api_key_configured": self.active_ai_key_configured(),
            "provider_ready": self.active_ai_provider_ready(),
            "timeout_seconds": self.AI_REQUEST_TIMEOUT_SECONDS,
            "provider_connect_timeout_seconds": self.AI_PROVIDER_CONNECT_TIMEOUT_SECONDS,
            "retry_times": self.AI_RETRY_TIMES,
            "provider_retry_times": self.AI_PROVIDER_RETRY_TIMES,
            "failover_fast_on_network_error": self.AI_FAILOVER_FAST_ON_NETWORK_ERROR,
            "temperature": self.AI_TEMPERATURE,
            "cache_ttl_seconds": self.AI_CACHE_TTL_SECONDS,
            "provider_fallbacks": self.AI_PROVIDER_FALLBACKS,
            "ready_providers": self.get_ready_ai_providers(),
            "fallback_chain": self.get_ai_provider_fallback_chain(),
        }

    def is_owner(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.OWNER_IDS

    def get_forward_targets(self) -> List[int]:
        """Return configured Telegram chat IDs that receive radar alerts."""
        return self.FORWARD_TO

    def ensure_data_dir(self) -> None:
        self.data_path.mkdir(parents=True, exist_ok=True)

    def public_runtime_summary(self) -> dict[str, Any]:
        """Safe configuration snapshot for logs and `/status`.

        This intentionally excludes Bot Token and API Keys.
        """
        return {
            "ai": self.public_ai_summary(),
            "provider": self.AI_PROVIDER,
            "model": self.effective_default_model,
            "radar_model": self.get_model_for_task("radar"),
            "private_model": self.get_model_for_task("private"),
            "task_model": self.get_model_for_task("task"),
            "chat_model": self.get_model_for_task("chat"),
            "vision_model": self.get_model_for_task("vision"),
            "active_ai_key_configured": self.active_ai_key_configured(),
            "active_ai_provider_ready": self.active_ai_provider_ready(),
            "log_level": self.LOG_LEVEL,
            "data_dir": self.DATA_DIR,
            "owners": len(self.OWNER_IDS),
            "forward_targets": len(self.FORWARD_TO),
            "admin_only_ai_test": self.ADMIN_ONLY_AI_TEST,
            "auto_ban": self.ENABLE_AUTO_BAN,
            "daily_report": self.ENABLE_DAILY_REPORT,
            "sender_profile_link": self.ENABLE_SENDER_PROFILE_LINK,
            "ai_filter": self.ENABLE_AI_FILTER,
            "heuristic_filter": self.ENABLE_HEURISTIC_FILTER,
            "timezone": self.DEFAULT_TIMEZONE,
            "max_message_length": self.MAX_MESSAGE_LENGTH,
            "ai_timeout_seconds": self.AI_REQUEST_TIMEOUT_SECONDS,
            "ai_provider_connect_timeout_seconds": self.AI_PROVIDER_CONNECT_TIMEOUT_SECONDS,
            "ai_retry_times": self.AI_RETRY_TIMES,
            "ai_provider_retry_times": self.AI_PROVIDER_RETRY_TIMES,
            "ai_failover_fast_on_network_error": self.AI_FAILOVER_FAST_ON_NETWORK_ERROR,
            "ai_cache_ttl_seconds": self.AI_CACHE_TTL_SECONDS,
        }


settings = Settings()
