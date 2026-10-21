"""Конфигурация приложения. Все параметры задаются через переменные окружения (12-factor)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Credit Conveyor"
    environment: str = "local"

    database_url: str = "postgresql+psycopg://conveyor:conveyor@localhost:5432/conveyor"

    jwt_secret: str = "change-me-in-production-please-32b"
    jwt_ttl_minutes: int = 480

    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Внешние интеграции (в проверяемой версии — локальные моки)
    mocks_base_url: str = "http://localhost:8001"
    integration_timeout_sec: float = 3.0
    integration_retries: int = 3
    integration_backoff_sec: float = 0.3

    # Конвейер
    pipeline_step_delay_sec: float = 1.5
    pipeline_poll_interval_sec: float = 1.0
    pipeline_max_enrichment_attempts: int = 3
    pipeline_enrichment_retry_delay_sec: float = 3.0
    pipeline_max_error_attempts: int = 3
    pipeline_error_retry_delay_sec: float = 10.0

    # Документы
    max_upload_bytes: int = 5 * 1024 * 1024

    # Опциональный ИИ-ассистент (только open-weights модели через Ollama)
    llm_enabled: bool = False
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:1.5b"
    llm_timeout_sec: float = 20.0

    log_level: str = "INFO"
    seed_on_start: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
