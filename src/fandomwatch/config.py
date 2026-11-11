"""Production configuration settings with environment variable bindings."""
import os
from typing import List


class Settings:
    """Enterprise platform configuration with fallback to environment variables."""

    def __init__(self):
        self.app_name: str = os.getenv("APP_NAME", "FandomWatch")
        self.app_env: str = os.getenv("APP_ENV", "production")
        self.version: str = "2.0.0"
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

        # Networking & API
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.cors_origins: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")

        # Database & Cache
        self.database_url: str = os.getenv(
            "DATABASE_URL", "sqlite:///fandomwatch.db"
        )
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Observability & Metrics
        self.prometheus_enabled: bool = os.getenv("PROMETHEUS_ENABLED", "true").lower() in ("true", "1")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

        # External Integrations
        self.youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")


settings = Settings()
