import os
from typing import List, Set, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Credentials
    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str | None = None
    
    # --- UPDATE: Changed default model to gpt-5-mini ---
    DEFAULT_MODEL: str = "gpt-5-mini"
    
    # Access Control & Routing
    OWNER_IDS: Set[int] = set()
    FORWARD_TO: List[int] = []
    
    # Paths
    DATA_DIR: str = "/app/data"
    
    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

    # Validator to handle single IDs or lists automatically
    @field_validator("OWNER_IDS", "FORWARD_TO", mode="before")
    @classmethod
    def parse_ids(cls, v: Union[str, int, list, set]) -> Union[List[int], Set[int]]:
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            if not v.strip(): return []
            try:
                # Remove brackets if user added them manually like "[123]"
                clean_v = v.replace("[", "").replace("]", "")
                return [int(x.strip()) for x in clean_v.split(",") if x.strip()]
            except:
                return []
        return v

    # The method required by handlers.py
    def get_forward_targets(self) -> List[int]:
        return self.FORWARD_TO

settings = Settings()