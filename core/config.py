"""Runtime configuration from environment variables. No pydantic — pure stdlib."""
import os


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    API_KEYS: list = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]
    ADMIN_TOKEN: str = os.environ.get("ADMIN_TOKEN", "")
    EMBEDDING_MODEL_PATH: str = os.environ.get(
        "EMBEDDING_MODEL_PATH", "/var/task/onnx_models/minilm/model.onnx"
    )
    RERANKER_MODEL_PATH: str = os.environ.get(
        "RERANKER_MODEL_PATH", "/var/task/onnx_models/reranker/model.onnx"
    )
    HOT_PATH_THRESHOLD: float = float(os.environ.get("HOT_PATH_THRESHOLD", "0.75"))
    L1_THRESHOLD: float = float(os.environ.get("L1_THRESHOLD", "0.65"))
    L2_THRESHOLD: float = float(os.environ.get("L2_THRESHOLD", "0.50"))
    MAX_HOT_PATHS: int = int(os.environ.get("MAX_HOT_PATHS", "70"))
    SERVICE_VERSION: str = os.environ.get("SERVICE_VERSION", "1.0.0")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
