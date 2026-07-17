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

    database_url: str = "postgresql+asyncpg://ruige:changeme@localhost:5432/ruige"
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
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    forgot_password_from_email: str = "noreply@ruige.app"
    forgot_password_token_expire_minutes: int = 60
    forgot_password_reset_url: str = "http://localhost:5173/reset-password"

    # ── 运行环境 ────────────────────────────────────────────────────
    environment: str = "development"  # development | production

    # ── 弹性 / 超时 / 重试配置 ──────────────────────────────────────
    llm_timeout_seconds: float = 120.0
    rerank_timeout_seconds: float = 60.0
    embed_timeout_seconds: float = 60.0
    retrieval_timeout_seconds: float = 30.0

    retry_max_attempts: int = 2
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0

    http_max_connections: int = 10  # 每服务 HTTP 连接池大小

    embedding_cache_max_size: int = 5000
    embedding_cache_ttl_seconds: int = 3600

    # ── 日志 / 可观测性 ──────────────────────────────────────────
    loki_url: str = ""  # 如 http://loki:3100，留空禁用 Loki 推送
    loki_service_name: str = "ruige-api"

    # ── Celery 异步任务 ──────────────────────────────────────────
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    celery_task_always_eager_local: bool = True  # 本地开发/测试时同步执行（无需 Redis）

    # ── OpenTelemetry 链路追踪 ──────────────────────────────────
    otlp_endpoint: str = "http://tempo:4318"

    # ── 数据库连接池 ─────────────────────────────────────────────
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600  # 1 小时回收连接，避免 PGBouncer 断连

    # ── 检索配置 ────────────────────────────────────────────────────
    vector_recall_k: int = 20       # 向量召回 Top-N
    fts_recall_k: int = 20          # 全文检索召回 Top-N
    llm_top_k: int = 5              # 最终送 LLM 的片段数

    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 30.0

    # ── 降级配置 ────────────────────────────────────────────────────
    degradation_llm_fallback_to_fts: bool = True
    degradation_enabled: bool = True
    degradation_cooldown_seconds: int = 60  # 降级后冷却窗口，阻止抖动回弹


settings = Settings()
