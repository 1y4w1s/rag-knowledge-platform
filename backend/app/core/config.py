"""应用配置（从环境变量 / .env 读取）。"""

from pathlib import Path

from typing import Optional

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
    # M8: JWT 有效小时数，生产建议 8h 或更短
    access_token_expire_hours: int = 8
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = "./uploads"
    upload_max_bytes: int = 20 * 1024 * 1024
    # NW-25：单库 uploads 账面上限（文档含 trash + 版本）；0=关闭总闸
    kb_quota_max_bytes: int = 10 * 1024**3
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    # B1 HyDE：query → LLM 生成假设文档 → 假设文档 embedding → 检索（默认关闭）
    hyde_enabled: bool = False
    # NW-9：对话生成 provider（deepseek | tongyi）；通义复用 tongyi_api_key
    chat_provider: str = "deepseek"
    tongyi_chat_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    tongyi_chat_model: str = "qwen-plus"
    tongyi_api_key: str = ""
    embedding_provider: str = "bge"
    embedding_model: str = "bge-small-zh-v1.5"   # 与 embedding_dim=512 对齐（bge-large 为 1024 维）
    embedding_dim: int = 512
    bge_api_url: str = "http://localhost:9997/v1/embeddings"
    bge_model_name: str = "bge-large-zh-v1.5"
    bge_model_path: str = "/app/models/bge-large-zh-v1.5"
    re_embed_token: str = ""
    # H2 orphan 扫描：宽限期 / 单次真删上限 / internal token（空=禁用）
    orphan_grace_hours: float = 24.0
    orphan_max_delete: int = 100
    orphan_scan_token: str = ""
    # H3 回收站：软删保留磁盘；过期 purge（天）/ 单次上限
    trash_retention_days: int = 30
    trash_purge_max_delete: int = 100
    # NW-20：对话 thread 保留期（天）；0=禁用；CLI scripts/purge_chat_threads.py
    chat_retention_days: int = 0
    chat_purge_max_delete: int = 100
    # NW-12：超龄 queued/processing → 干跑扫描 / --apply 标 failed（不上 Beat）
    ingest_stale_queued_minutes: float = 60.0
    ingest_stale_processing_minutes: float = 120.0
    ingest_stale_max_apply: int = 100
    retrieval_min_top1_similarity: float = 0.35
    # A4：字面无重叠时的语义拒答兜底（原 relevance.SIMILARITY_FALLBACK_THRESHOLD）
    # 实验L：灰色带下限 0.45（实测 0.50 全量 -5.94pp 回退；0.45 = 84.76% 最优）
    relevance_similarity_fallback: float = 0.45
    # 灰色带语义兜底上限（AC-4）：无词面重叠但 sim ≥ 此值视为高相似假阳性，仍丢弃
    relevance_high_sim_reject: float = 0.9
    rrf_k: int = 60
    rrf_vector_weight: float = 1.0   # 实测：1.5 反而降 0.72pp，维持 1.0
    rrf_fts_weight: float = 1.5     # A4 扫参：1.2→1.5，Enterprise Hit@3 +1（同环境）
    rerank_enabled: bool = False  # A2 真路径默认关；开前先 diagnose --rerank
    # off=今日默认 RRF；always=旧 enabled+skip；conditional=仅歧义精排
    rerank_policy: str = "off"  # off | always | conditional
    rerank_provider: str = "bge"  # bge | mock | tongyi
    rerank_model: str = "BAAI/bge-reranker-base"
    rerank_input_top_n: int = 20
    bge_rerank_cache_dir: str = ""  # 空=fastembed 默认缓存；可指本地目录
    ocr_enabled: bool = True
    ocr_max_pages: int = 30
    # B1：文字层 PDF 页眉/页脚降噪；可关回退整页 extract_text
    pdf_layout_denoise_enabled: bool = True
    # B2：大表行窗切分 + PDF 跨页同表合并；关则≈F3 旧行为
    table_chunk_split_enabled: bool = True
    table_parent_max_chars: int = 8000
    table_row_overlap: int = 1
    chunk_max_chars: int = 1200  # 单 chunk 最大字符数，入库时生效；环境变量 CHUNK_MAX_CHARS
    # NW-27：citation.excerpt 脱敏（先 mask 后截断）；关=仅截断旧行为
    citation_redact_enabled: bool = True
    # NW-34：送模【检索片段】scrub（复用 mask_pii）；默认关；仍算出境 ≠ NW-33
    llm_context_redact_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    forgot_password_from_email: str = "noreply@ruige.app"
    forgot_password_token_expire_minutes: int = 60
    forgot_password_reset_url: str = "http://localhost:5173/reset-password"

    # ── Webhook 安全（Phase 3 SSRF 加固）────────────────────────────
    # Webhook 域名白名单（空列表=不限制）；支持主域名及 *.domain 子域名匹配
    webhook_allowed_domains: list[str] = []

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

    # ── 全局限流（TECH-SEC P1）────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60

    # ── 检索配置 ────────────────────────────────────────────────────
    vector_recall_k: int = 30       # 向量召回 Top-N（2026-07-18 从 20 调升到 30）
    fts_recall_k: int = 30          # 全文检索召回 Top-N（同步调升）
    llm_top_k: int = 8              # 最终送 LLM 的片段数（2026-07-18 从 5 调升到 8）
    self_verify_enabled: bool = False  # 生成后自动验证（额外 DeepSeek 调用）
    citation_density_check_enabled: bool = True  # 第2层：生成后校验引用密度并重生成
    citation_density_regenerate_limit: int = 1   # 低密度时最多重生成次数

    # ── 消融实验：检索融合模式 ───────────────────────────────────────
    # "rrf" → 向量+FTS+RRF（生产默认）；"concat" → 简单拼接去重（消融②）；
    # "vector_only" → 纯向量，不调 FTS（消融①）
    retrieval_fusion_mode: str = "rrf"

    # ── 缓存配置 ────────────────────────────────────────────────────
    query_cache_ttl_seconds: int = 300     # 检索 chunk 结果缓存 TTL（秒）
    query_cache_max_size: int = 5000       # 进程内缓存最大条目数
    llm_response_cache_ttl_seconds: int = 600  # LLM 响应缓存 TTL（秒）；0=关闭

    # A1 多 query：默认 off 单问；always≡旧 enabled；conditional=短问/miss 才扩
    query_rewrite_enabled: bool = False
    query_rewrite_policy: str = "off"  # off | always | conditional
    query_rewrite_max_variants: int = 3  # 含原问，上限总问法数
    query_rewrite_variant_weight: float = 0.7  # 变体向量路相对权重，防稀释原问

    # A3 条款号 / 文档名路由：规则路径；默认开，可关回退
    clause_route_enabled: bool = True
    clause_route_extra_slots: int = 5  # 追加到融合池的槽位
    clause_route_limit: int = 10  # 路由召回上限

    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 30.0

    # ── 降级配置 ────────────────────────────────────────────────────
    degradation_llm_fallback_to_fts: bool = True
    degradation_enabled: bool = True
    degradation_cooldown_seconds: int = 60  # 降级后冷却窗口，阻止抖动回弹

    # ── A1 Agentic LLM Planner ────────────────────────────────────
    agent_llm_planner_enabled: bool = True
    agent_llm_planner_model: Optional[str] = None

    # ── E2 Agentic Reflection ─────────────────────────────────────
    agent_max_reflections: int = 3

    # ── E3 Agentic Memory ─────────────────────────────────────────
    agent_memory_enabled: bool = True

    # ── E4 External Tools ─────────────────────────────────────────
    external_tools_enabled: bool = False
    agent_db_url: str = ""
    agent_max_external_calls_per_conversation: int = 3

    # ── C1 Vision LLM ──────────────────────────────────────────────
    tongyi_vl_model: str = "qwen-vl-plus"

    # ── D1 GraphRAG ─────────────────────────────────────────────────
    graph_recall_enabled: bool = False  # 2026-07-31 实测：图谱召回质量差（sim 0.25-0.3 噪音 130+，正确答案被淹没），L4 无提升，回滚


settings = Settings()
