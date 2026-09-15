from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Bitcoin Intelligence API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://bitcoin:bitcoin@db:5432/bitcoin"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 90

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "nomic-embed-text"
    embedding_timeout_seconds: int = 90
    chunk_size_chars: int = 1800
    chunk_overlap_chars: int = 250
    index_interval_seconds: int = 300

    crawl_interval_seconds: int = 3600
    crawl_max_pages_per_source: int = 20
    crawl_request_timeout_seconds: int = 20
    crawl_user_agent: str = "BitcoinIntelligenceBot/0.2"
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
