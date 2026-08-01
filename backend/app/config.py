from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./matchiq.db"
    nba_api_key: str = ""
    football_data_api_key: str = ""
    artifact_dir: Path = Path("./artifacts")
    allowed_origins: str = "http://localhost:5173,http://localhost:4173"

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
