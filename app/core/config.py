from pydantic_settings import BaseSettings
from pydantic import validator
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str
    API_KEYS: str
    ADMIN_TOKEN: str
    EMBEDDING_MODEL_PATH: str = "/app/models/minilm/model.onnx"
    RERANKER_MODEL_PATH: str = "/app/models/reranker/model.onnx"
    HOT_PATH_THRESHOLD: float = 0.75
    L1_THRESHOLD: float = 0.65
    L2_THRESHOLD: float = 0.50
    MAX_HOT_PATHS: int = 70
    MIN_HITS_PER_WEEK: int = 50
    CORS_ORIGINS: str = "*"
    SERVICE_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    @validator("DATABASE_URL", "API_KEYS", "ADMIN_TOKEN")
    def must_be_set(cls, v, field):
        if not v or not v.strip():
            raise ValueError(f"{field.name} is required and cannot be empty")
        return v

    def api_keys_list(self) -> List[str]:
        return [k.strip() for k in self.API_KEYS.split(",") if k.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
