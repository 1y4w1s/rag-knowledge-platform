"""044 — 模型↔库对齐（D2）：evaluation_runs 建表迁移 + 结构性对齐

Revision ID: 044_model_alignment
Revises: f5fe692ccc9d
Create Date: 2026-08-05

背景（masterplan 主题 D · D1 审计）：
  1. P0-06：evaluation_runs 无建表迁移，fresh 环境 `alembic upgrade head` 后该表缺失
     → 本迁移补建表（IF NOT EXISTS，兼容 benchmark 脚本已建表的现有库）。
  2. 模型↔库结构性差异（D1 §1/§5）：
     - evaluation_runs.run_id：模型声明唯一索引，库为普通索引 + 独立唯一约束 → 收敛为唯一索引
     - evaluation_runs.mode / triggered_by：模型带 comment，库无 → 补 comment
     - chat_feedback.feedback_text：模型带 comment，库无 → 补 comment
     - agent_memories 唯一约束：模型名 uq_user_memory_key，库为 PG 默认名
       agent_memories_user_id_key_key（041 之前由其他路径建表）→ rename 对齐
     - documents.progress_percent：模型 Integer，库 SMALLINT（036）→ 升为 Integer

安全约束：
  - 不含任何 DROP TABLE / DROP INDEX 破坏性操作（转换逻辑均以约束存在为前提，DO 块条件执行）
  - embedding_backup（33 万行孤儿表）由 alembic/env.py include_object 显式排除，本迁移不触碰
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "044_model_alignment"
down_revision: str | None = "f5fe692ccc9d"
branch_labels: str | None = None
depends_on: str | None = None

# evaluation_runs 建表（fresh 环境；现有库 IF NOT EXISTS 跳过）。
# 对齐 evaluation_run.py 模型 + 当前库 server_default（mode/triggered_by/total_queries/skipped/created_at）。
_CREATE_EVALUATION_RUNS = """
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id UUID NOT NULL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    dataset_name VARCHAR(128) NOT NULL,
    mode VARCHAR(32) NOT NULL DEFAULT 'retrieval',
    git_sha VARCHAR(64),
    total_queries INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    hit_at_1 DOUBLE PRECISION,
    hit_at_3 DOUBLE PRECISION,
    hit_at_5 DOUBLE PRECISION,
    mrr DOUBLE PRECISION,
    precision_at_k DOUBLE PRECISION,
    recall_at_k DOUBLE PRECISION,
    map_score DOUBLE PRECISION,
    correct_rejection_rate DOUBLE PRECISION,
    generation_correctness DOUBLE PRECISION,
    generation_faithfulness DOUBLE PRECISION,
    generation_hallucination_rate DOUBLE PRECISION,
    generation_citation_accuracy DOUBLE PRECISION,
    p50_latency_ms DOUBLE PRECISION,
    p95_latency_ms DOUBLE PRECISION,
    p99_latency_ms DOUBLE PRECISION,
    throughput_qps DOUBLE PRECISION,
    breakdown_domain JSONB,
    breakdown_type JSONB,
    notes TEXT,
    triggered_by VARCHAR(32) DEFAULT 'manual',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
)
"""

# run_id 唯一索引（模型声明 unique=True, index=True 的落库形态）
_CREATE_RUN_ID_UNIQUE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_evaluation_runs_run_id "
    "ON evaluation_runs (run_id)"
)

# dataset_name 索引（模型声明 index=True）
_CREATE_DATASET_NAME_IDX = (
    "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_dataset_name "
    "ON evaluation_runs (dataset_name)"
)

# 现有库（benchmark 脚本建表）收敛：唯一约束 + 普通索引 → 唯一索引。
# fresh 环境（044 建表，无 run_id_key 约束）条件不成立，自动跳过。
_CONVERT_RUN_ID_KEY = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'evaluation_runs_run_id_key'
          AND conrelid = 'evaluation_runs'::regclass
    ) THEN
        ALTER TABLE evaluation_runs DROP CONSTRAINT evaluation_runs_run_id_key;
        DROP INDEX IF EXISTS ix_evaluation_runs_run_id;
        CREATE UNIQUE INDEX ix_evaluation_runs_run_id ON evaluation_runs (run_id);
    END IF;
END $$;
"""

# agent_memories 唯一约束改名对齐模型（fresh 环境 041 已建 uq_user_memory_key，条件不成立跳过）
_RENAME_MEMORY_UQ = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'agent_memories_user_id_key_key'
          AND conrelid = 'agent_memories'::regclass
    ) THEN
        ALTER TABLE agent_memories
            RENAME CONSTRAINT agent_memories_user_id_key_key TO uq_user_memory_key;
    END IF;
END $$;
"""


def upgrade() -> None:
    # 1. evaluation_runs 建表 + 索引（P0-06，fresh 环境）
    op.execute(_CREATE_EVALUATION_RUNS)
    op.execute(_CREATE_RUN_ID_UNIQUE)
    op.execute(_CREATE_DATASET_NAME_IDX)

    # 2. 现有库 run_id 索引形态收敛：唯一约束 + 普通索引 → 唯一索引
    op.execute(_CONVERT_RUN_ID_KEY)

    # 3. comment 对齐（幂等）
    op.execute("COMMENT ON COLUMN evaluation_runs.mode IS 'retrieval | generation | full'")
    op.execute("COMMENT ON COLUMN evaluation_runs.triggered_by IS 'manual | ci_fast | ci_full | nightly'")
    op.execute("COMMENT ON COLUMN chat_feedback.feedback_text IS '可选评论文本'")

    # 4. agent_memories 唯一约束改名对齐模型
    op.execute(_RENAME_MEMORY_UQ)

    # 5. documents.progress_percent SMALLINT → Integer（036 建 SMALLINT，模型 Integer）
    op.alter_column(
        "documents",
        "progress_percent",
        existing_type=sa.SmallInteger(),
        type_=sa.Integer(),
        postgresql_using="progress_percent::integer",
    )


def downgrade() -> None:
    # best-effort 回滚：恢复 run_id 为「唯一约束 + 普通索引」形态（不删表、不删数据）
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'evaluation_runs_run_id_key'
                  AND conrelid = 'evaluation_runs'::regclass
            ) THEN
                DROP INDEX IF EXISTS ix_evaluation_runs_run_id;
                ALTER TABLE evaluation_runs
                    ADD CONSTRAINT evaluation_runs_run_id_key UNIQUE (run_id);
                CREATE INDEX ix_evaluation_runs_run_id ON evaluation_runs (run_id);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_user_memory_key'
                  AND conrelid = 'agent_memories'::regclass
            ) THEN
                ALTER TABLE agent_memories
                    RENAME CONSTRAINT uq_user_memory_key TO agent_memories_user_id_key_key;
            END IF;
        END $$;
        """
    )
    op.execute("COMMENT ON COLUMN evaluation_runs.mode IS NULL")
    op.execute("COMMENT ON COLUMN evaluation_runs.triggered_by IS NULL")
    op.execute("COMMENT ON COLUMN chat_feedback.feedback_text IS NULL")
    op.alter_column(
        "documents",
        "progress_percent",
        existing_type=sa.Integer(),
        type_=sa.SmallInteger(),
        postgresql_using="progress_percent::smallint",
    )
    # 注意：downgrade 不 drop evaluation_runs 表（fresh 环境由 044 建表，现有库为
    # benchmark 脚本建表，均不应由迁移删除）。
