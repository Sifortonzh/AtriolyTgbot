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
    OPENAI_API_KEY: str | None = None

    # AI
    DEFAULT_MODEL: str = "gpt-5-mini"
    MAX_MESSAGE_LENGTH: int = 1200
    AI_REQUEST_TIMEOUT_SECONDS: float = 30.0
    AI_RETRY_TIMES: int = 2
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

    @field_validator("MAX_MESSAGE_LENGTH")
    @classmethod
    def validate_max_message_length(cls, value: int) -> int:
        return max(100, min(value, 12000))

    @field_validator("AI_RETRY_TIMES")
    @classmethod
    def validate_ai_retry_times(cls, value: int) -> int:
        return max(0, min(value, 5))

    @field_validator("AI_TEMPERATURE")
    @classmethod
    def validate_ai_temperature(cls, value: float) -> float:
        return max(0.0, min(value, 2.0))

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
        """Parse Telegram ID collections from env-friendly formats.

        Supported examples:
        - 123456789
        - "123456789"
        - "123456789,987654321"
        - "[123456789, 987654321]"
        - [123456789, "987654321"]
        """
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

    def is_owner(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.OWNER_IDS

    def get_forward_targets(self) -> List[int]:
        """Return configured Telegram chat IDs that receive radar alerts."""
        return self.FORWARD_TO

    def ensure_data_dir(self) -> None:
        self.data_path.mkdir(parents=True, exist_ok=True)

    def public_runtime_summary(self) -> dict[str, Any]:
        """Safe configuration snapshot for logs and `/status`.

        This intentionally excludes Bot Token and API Key.
        """
        return {
            "model": self.DEFAULT_MODEL,
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
        }


settings = Settings()