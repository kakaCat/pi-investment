-- RFC 014: 公告板独立存储（脱离 Agent OS memory 复用）
-- 2026-09-08: 公告板帖不再以 memory 行（tag office:board）承载，独立成表。
-- 根因：memory 语义搜索 tag 过滤不严格 → 普通记忆被误捞进公告板默认 open；
--       无 metadata 的记忆无法走状态机/权限/乐观锁 → 只增不减。
-- 状态机与旧 board-tools.ts 保持一致：open→[claim,drop]; claimed→[pause,blocked,complete,drop];
-- paused→[claim,drop]; blocked→[claim,complete,drop]; done/dropped/archived 终态。

CREATE TABLE IF NOT EXISTS board_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    display_title TEXT,                    -- edit 动作改标题时存这里（title 为原文）
    kind VARCHAR(20) NOT NULL DEFAULT 'finding',  -- finding/question/review/proposal（兼容 task/bug 等历史值）
    status VARCHAR(20) NOT NULL DEFAULT 'open',   -- open/claimed/paused/blocked/done/dropped/archived
    author VARCHAR(100),                   -- 发帖窗口（w-xxx 或 agent 角色 id）
    assignee VARCHAR(100),                 -- 认领窗口
    revision INTEGER NOT NULL DEFAULT 1,   -- 乐观锁
    claim_count INTEGER NOT NULL DEFAULT 0,
    claimed_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    status_reason TEXT,                    -- pause/blocked/complete 的说明
    drop_reason TEXT,                      -- drop 原因
    moderation_log JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{timestamp,action,actor,note}]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_board_posts_status ON board_posts(status);
CREATE INDEX IF NOT EXISTS idx_board_posts_kind ON board_posts(kind);
CREATE INDEX IF NOT EXISTS idx_board_posts_assignee ON board_posts(assignee);
CREATE INDEX IF NOT EXISTS idx_board_posts_created ON board_posts(created_at DESC);

COMMENT ON TABLE board_posts IS 'RFC 014 公告板独立存储：帖子+状态机+审计日志，脱离 memories 表';
