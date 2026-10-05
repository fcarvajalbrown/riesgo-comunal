from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://riesgo:riesgo@127.0.0.1:5440/riesgo"
    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_minutes: int = 720
    upload_dir: str = "data/uploads"
    geocoder_url: str = "https://nominatim.openstreetmap.org/search"
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000"

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 120
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None

    dmc_user: str | None = None
    dmc_token: str | None = None

    http_timeout_seconds: float = 90
    http_user_agent: str = "riesgo-comunal/0.1 (plataforma municipal de informacion de riesgo)"
    scheduler_enabled: bool = True

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    @property
    def embeddings_enabled(self) -> bool:
        return bool(self.embedding_base_url and self.embedding_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
