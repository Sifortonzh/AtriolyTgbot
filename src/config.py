import os
from pydantic_settings import BaseSettings
from typing import List, Set

class Settings(BaseSettings):
	TELEGRAM_BOT_TOKEN: str
	OPENAI_API_KEY: str | None = None
	OWNER_IDS: Set[int] = set()
	FORWARD_TO: List[int] = []
	DEFAULT_MODEL: str = "gpt-5-mini"
	
	class Config:
		env_file = ".env"

settings = Settings()
