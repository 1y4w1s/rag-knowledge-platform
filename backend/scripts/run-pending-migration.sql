-- standalone SQL migration for 038_add_message_status
-- 手动运行：psql -U ruige -d ruige -f run-pending-migration.sql
-- 或：docker compose exec postgres psql -U ruige -f /app/run-pending-migration.sql

BEGIN;

-- 1. 创建 ENUM 类型（幂等）
DO $$ BEGIN
    CREATE TYPE message_status AS ENUM ('pending', 'completed', 'interrupted');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 2. 添加列
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS status message_status;

-- 3. 回填已有行
UPDATE chat_messages SET status = 'completed' WHERE status IS NULL;

-- 4. 设 NOT NULL
ALTER TABLE chat_messages ALTER COLUMN status SET NOT NULL;

COMMIT;
