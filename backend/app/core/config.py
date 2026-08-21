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
    # M8-I3：OOXML zip 解压前压缩炸弹防护（docx/xlsx/pptx；≤0 关闭该防护）
    zip_max_uncompressed_bytes: int = 1 * 1024**3      # 解压后总大小上限（1 GiB）
    zip_max_compression_ratio: float = 200.0           # 解压后总大小 / 压缩后总大小上限
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
    bge_model_path: str = "/app/models/bge-large-zh-v1.5"  # 仅 embedding_dim=1024 分支使用
    bge_en_model: str = ""  # 空=默认 BAAI/bge-small-en-v1.5（P1-11 方案 B）
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
    # M5 条件灰色带：查询有词面锚点时灰色带下限收紧到该值（M5.4 定档 0.65）；
    # 无锚点（GQ-47 类纯语义查询）保持 relevance_similarity_fallback 宽带
    relevance_grey_anchor_lo: float = 0.65
    # M5.3: static deterministic variants injected when LLM is degraded
    static_variant_rules_path: str = "app/services/rag/static_variant_rules.json"
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
    # NW-34：送模【检索片段】scrub（复用 mask_pii）；P2-R16 默认开；仍算出境 ≠ NW-33
    llm_context_redact_enabled: bool = True
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
    # P1-S2：webhook secret 的 at-rest 加密密钥（独立专用，禁止与 JWT/LLM 等混用）
    webhook_encryption_secret: str = ""

    # ── 运行环境 ────────────────────────────────────────────────────
    environment: str = "development"  # development | production

    # ── 弹性 / 超时 / 重试配置 ──────────────────────────────────────
    llm_timeout_seconds: float = 120.0
    rerank_timeout_seconds: float = 60.0
    embed_timeout_seconds: float = 60.0
    # P0-11 连接超时守卫：外部连接显式 socket/connect timeout，探活不挂死
    redis_socket_timeout_seconds: float = 5.0   # 单次 Redis 操作 socket 超时（秒）
    redis_connect_timeout_seconds: float = 5.0  # Redis TCP 建连超时（秒）
    db_connect_timeout_seconds: float = 10.0    # asyncpg 建连超时（默认 60s 过长）
    db_pool_timeout_seconds: float = 10.0       # SQLAlchemy 连接池排队等待超时（默认 30s）

    retry_max_attempts: int = 2
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0

    http_max_connections: int = 10  # 每服务 HTTP 连接池大小

    embedding_cache_max_size: int = 5000
    embedding_cache_ttl_seconds: int = 3600

    # ── 日志 / 可观测性 ──────────────────────────────────────────
    loki_url: str = ""  # 如 http://loki:3100，留空禁用 Loki 推送
    # C1 收口：/metrics 静态令牌（原 METRICS_BEARER_TOKEN env；空=端点 fail-closed 401）
    metrics_bearer_token: str = ""
    loki_service_name: str = "ruige-api"

    # ── Celery 异步任务 ──────────────────────────────────────────
    # C1 收口：统一 Redis 连接 URL（原 REDIS_URL env；compose 已映射）；
    # 空时回退 CELERY_BROKER_URL env，再回退 localhost:6379/1（兼容旧默认）
    redis_url: str = ""
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
    # C1 收口：限流后端（memory|redis），默认 redis（多副本计数）；
    # RATE_LIMIT_BACKEND env 仍可覆盖（测试/部署显式 memory）
    rate_limit_backend: str = "redis"
    # P0-05 XFF 信任链：可信反代跳数。0=API 直连（忽略 X-Forwarded-For，防伪造）；
    # 1=单跳 nginx（docker-compose 生产默认）；多跳按实际代理层数配置。
    trusted_proxy_count: int = 0

    # ── 邀请码安全（P2-P3）──────────────────────────────────────────
    # 随机后缀位数（默认 8，防枚举；配置低于 8 时按 8 生效）
    invite_code_random_length: int = 8
    # 默认过期小时数：发码未传 expires_at 时生效；0=管理员显式选择永不过期
    invite_code_default_expire_hours: int = 168

    # ── 检索配置 ────────────────────────────────────────────────────
    vector_recall_k: int = 30       # 向量召回 Top-N（2026-07-18 从 20 调升到 30）
    fts_recall_k: int = 30          # 全文检索召回 Top-N（同步调升）
    llm_top_k: int = 8              # 最终送 LLM 的片段数（2026-07-18 从 5 调升到 8）
    self_verify_enabled: bool = False  # 生成后自动验证（额外 DeepSeek 调用）
    # G1 Critic：claim 级规则校验（默认关；不替代、不默认打开 self_verify）
    rag_critic_enabled: bool = False
    rag_critic_mode: str = "rules"  # rules | llm（主开关开时才读；生产勿默认 llm）
    rag_critic_max_claims: int = 12
    rag_critic_on_fail: str = "fail_closed"  # fail_closed | annotate_only
    citation_density_check_enabled: bool = True  # 第2层：生成后校验引用密度并重生成
    citation_density_regenerate_limit: int = 1   # 低密度时最多重生成次数

    # ── 消融实验：检索融合模式 ───────────────────────────────────────
    # "rrf" → 向量+FTS+RRF（生产默认）；"concat" → 简单拼接去重（消融②）；
    # "vector_only" → 纯向量，不调 FTS（消融①）
    retrieval_fusion_mode: str = "rrf"

    # ── 缓存配置 ────────────────────────────────────────────────────
    # C1 收口：检索/LLM 响应缓存后端（memory|redis）；原 CACHE_BACKEND env
    cache_backend: str = "memory"
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
    degradation_enabled: bool = True
    degradation_cooldown_seconds: int = 60  # 降级后冷却窗口，阻止抖动回弹

    # ── A1 Agentic LLM Planner ────────────────────────────────────
    agent_llm_planner_enabled: bool = True
    agent_llm_planner_model: Optional[str] = None

    # ── L3 Observation-driven NextActionPlanner（全部默认关；可回滚）──
    agent_l3_next_action_enabled: bool = False
    agent_l3_dynamic_tools_enabled: bool = False
    agent_l3_evidence_state_enabled: bool = False
    # 轨迹摘要也默认 False（与本批「全 flag 关」一致；开观测另开）
    agent_l3_trajectory_trace_enabled: bool = False
    # 0 = 对齐当次 max_steps；>0 为硬上限（防只规划不执行）
    agent_l3_max_planner_calls: int = 0
    agent_l3_critic_retrieval_enabled: bool = False

    # ── L4 Evidence-Driven Local Intelligence（W1 仅占位；全部默认关）──
    agent_l4_fact_decomposition_enabled: bool = False
    agent_l4_evidence_matcher_enabled: bool = False
    agent_l4_contradiction_enabled: bool = False
    agent_l4_stop_policy_enabled: bool = False
    agent_l4_local_model_profile_enabled: bool = False
    agent_l4_multimodal_evidence_enabled: bool = False

    # ── E2 Agentic Reflection ─────────────────────────────────────
    agent_max_reflections: int = 3
    # M1 候选③ 漂移守卫主开关（默认关；W2 复测轮开启，劣化立即置回 False）
    agent_decompose_drift_recovery: bool = False
    # 每漂移子查询 S1 收敛改写上限（防 LLM 非确定性放大/改写死循环）
    agent_decompose_drift_max_rewrites: int = 1

    # ── E3 Agentic Memory ─────────────────────────────────────────
    agent_memory_enabled: bool = True
    # T5 Agent Memory Governance
    agent_memory_suppress_seconds: int = 604800
    agent_memory_churn_threshold: int = 3
    agent_memory_churn_window_seconds: int = 86400
    agent_memory_rule_confidence: float = 0.7
    agent_memory_lang_cjk_ratio: float = 0.6
    agent_memory_depth_min_searches: int = 2

    # ── T6 W2 Working Memory（滑动窗口）────────────────────────────
    agent_memory_window_max_messages: int = 12   # 消息数预算（= 6 轮）；0=禁用消息数裁剪
    agent_memory_window_token_budget: int = 22400  # token 预算（64k × 35%，与 generation.py 口径一致）；0=禁用 token 裁剪
    agent_memory_window_min_keep: int = 2        # 至少保留最近消息数（防止双预算把最新一轮也裁掉）
    agent_memory_window_summary_prefix: str = "wm_summary"  # 摘要占位 key 前缀
    agent_memory_window_summary_max: int = 3     # 单次最多产出的摘要占位条数

    # ── T6 W3 Importance Tiering（重要性评分与分层）──────────────────
    agent_memory_importance_promote_threshold: float = 0.7    # long_term → working 促升阈值（score >= 该值）
    agent_memory_importance_demote_threshold: float = 0.35   # working → long_term 促降阈值（score < 该值）；必须 < promote
    agent_memory_importance_source_weight: float = 0.30      # source 优先级因子权重
    agent_memory_importance_recency_weight: float = 0.25     # 最近使用因子权重
    agent_memory_importance_frequency_weight: float = 0.20   # 频次因子权重（confidence 代理）
    agent_memory_importance_feedback_weight: float = 0.15    # 用户反馈因子权重
    agent_memory_importance_governance_weight: float = 0.10  # 治理状态因子权重
    agent_memory_importance_recency_half_life_days: float = 14.0  # 最近使用半衰期（天）
    agent_memory_importance_feedback_penalty: float = 0.4    # suppressed / conflicted 的反馈因子值
    agent_memory_importance_churn_penalty: float = 0.5       # churn_count >= 阈值时的治理因子值
    # ── T6 W4 Memory Summary（结构化摘要）──────────────────────────
    agent_memory_summary_max_field_chars: int = 120   # 单个字符串字段最大字符数；超长截断并追加标记
    agent_memory_summary_max_items: int = 20          # 单列表最大保留条目数；超出追加标记
    agent_memory_summary_max_depth: int = 3           # 嵌套 dict/list 最大深度；超出整棵子树替换为标记
    agent_memory_summary_max_total_chars: int = 800   # 摘要 JSON 序列化最大字符数；超限按 §4.2 规则再压缩
    agent_memory_summary_truncation_marker: str = "..."  # 截断标记（ASCII，避免编码/序列化差异）

    # ── E4 External Tools ─────────────────────────────────────────
    external_tools_enabled: bool = False
    search_api_key: str = ""  # C1 收口：web_search 第三方凭据（原 SEARCH_API_KEY env 兼容）
    agent_max_external_calls_per_conversation: int = 3

    # ── G1 Tool Failure Replan ───────────────────────────────────
    agent_max_tool_replans: int = 2  # 工具失败提示重规划上限；0=关闭（保留现状）

    # ── G2 Agent Tool Guard（工具级熔断 / 限流 / token 估算）──────────────
    agent_tool_breaker_overrides: dict[str, dict[str, int | float]] = {
        "web_search": {"failure_threshold": 2, "recovery_timeout": 15},
    }
    agent_tool_max_calls_per_run_override: dict[str, int] = {}
    agent_tool_window_rate_limit_enabled: bool = True
    agent_tool_window_rate_limit: dict[str, dict[str, int]] = {
        "web_search": {"max": 60, "window_seconds": 3600},
    }
    # G2-usage: real provider usage collection master switch
    llm_usage_collection_enabled: bool = True

    # ── B2 Agent 生命周期清扫（P1-03）────────────────────────────
    # running run 超过该时长视为 crash/断线残留，清扫器强制 failed
    agent_run_stale_minutes: int = 15
    # pending 审批 TTL（惰性判定：created_at + TTL；resolve 入口先判过期）
    agent_approval_ttl_hours: float = 24.0
    # H1/M17：Member 编辑模式 FAQ 草稿生成配额（0=关闭配额闸）
    agent_member_faq_thread_quota: int = 3   # 每 thread 最多 pending adopt_faq 卡数
    agent_member_faq_daily_quota: int = 10   # 每日最多创建 adopt_faq 审批数
    # 同 thread 生成锁/SSE 槽位持有上限（分布式锁 TTL，30min 兜底自动过期）
    agent_run_lock_ttl_seconds: int = 1800

    # ── B3 锁后端（memory=显式单 worker；redis=多 worker 必须）────
    lock_backend: str = "memory"

    # ── C1 Vision LLM ──────────────────────────────────────────────
    tongyi_vl_model: str = "qwen-vl-plus"

    # ── M1 候选②：低置信话术相似度上限阈值（≥此值→强命中，非 low）────
    relevance_low_sim_ceiling: float = 0.5
    # ── M1 候选①：送模上下文预算裁剪（0=不启用；>0 时只丢低分尾部）────
    llm_context_budget_chars: int = 0

    # ── M2 C1：证据充分性判定 observation mode 开关（默认关；W1 复测轮开启）────
    agent_evidence_sufficiency_obs: bool = False
    # ── M2 C2：证据不足自适应重检开关（默认关；开启后证据不足走 S1 改写 / S2 整题直检）────
    agent_evidence_strategy_enabled: bool = False

    # ── D1 GraphRAG ─────────────────────────────────────────────────
    graph_recall_enabled: bool = False  # 2026-07-31 实测：图谱召回质量差（sim 0.25-0.3 噪音 130+，正确答案被淹没），L4 无提升，回滚
    # D1 临时 OOM 保护：跳过实体抽取（原 SKIP_ENTITY_EXTRACT env；恢复实体图谱时删除）
    skip_entity_extract: bool = False


settings = Settings()
