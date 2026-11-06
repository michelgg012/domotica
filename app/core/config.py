from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    db_pool_min: int = 1
    db_pool_max: int = 10
    log_level: str = "INFO"
    jwt_secret: str = Field(min_length=32)
    jwt_expira_min: int = 480

settings = Settings()