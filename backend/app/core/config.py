"""应用配置（从环境变量 / .env 读取）。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _utf8_env_files() -> tuple[str, ...]:
    """仅加载 UTF-8 可读的 .env，避免 Windows GBK 文件阻断 pytest/CI。"""
    found: list[str] = []
    for rel in (".env", "../.env"):
        path = Path(rel)
        if not path.is_file():
            continue
        try:
            path.read_text(encoding="utf-8")
            found.append(rel)
        except UnicodeDecodeError:
            pass
    return tuple(found)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_utf8_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://zhiku:changeme@localhost:5432/zhiku"
    jwt_secret: str = "replace-with-a-long-random-string"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = "./uploads"
    upload_max_bytes: int = 20 * 1024 * 1024
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    tongyi_api_key: str = ""
    embedding_provider: str = "tongyi"
    embedding_model: str = "text-embedding-v2"
    embedding_dim: int = 1536
    re_embed_token: str = ""
    retrieval_min_top1_similarity: float = 0.35
    rrf_k: int = 60
    rrf_vector_weight: float = 1.0
    rrf_fts_weight: float = 1.2
    rerank_enabled: bool = True
    rerank_provider: str = "tongyi"
    rerank_model: str = "qwen3-rerank"
    rerank_input_top_n: int = 20
    ocr_enabled: bool = True
    ocr_max_pages: int = 30


settings = Settings()
