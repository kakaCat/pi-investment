-- Migration: 008_create_notifications
-- Description: Create notification system tables
-- Created: 2026-08-14

-- ============================================================================
-- UP Migration
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table 1: notification_providers (通知提供商)
CREATE TABLE notification_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 2: notification_channels (通知渠道)
CREATE TABLE notification_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_id UUID NOT NULL REFERENCES notification_providers(id) ON DELETE CASCADE,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 3: notification_logs (通知日志)
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
    title VARCHAR(255),
    content TEXT,
    status VARCHAR(32) NOT NULL,
    message_id VARCHAR(255),
    error TEXT,
    metadata JSONB DEFAULT '{}',
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for notification_channels
CREATE INDEX idx_channels_provider ON notification_channels(provider_id);
CREATE INDEX idx_channels_code ON notification_channels(code);
CREATE INDEX idx_channels_enabled ON notification_channels(enabled);

-- Indexes for notification_logs
CREATE INDEX idx_logs_channel ON notification_logs(channel_id);
CREATE INDEX idx_logs_status ON notification_logs(status);
CREATE INDEX idx_logs_created ON notification_logs(created_at DESC);

-- Constraints
ALTER TABLE notification_logs ADD CONSTRAINT check_status
    CHECK (status IN ('pending', 'sent', 'failed'));

-- Insert initial data: Feishu provider
INSERT INTO notification_providers (code, name, config) VALUES
('feishu', '飞书', '{
  "bot": {
    "app_id": "",
    "app_secret": ""
  }
}');

-- Insert initial channels (using environment variables in config)
INSERT INTO notification_channels (provider_id, code, name, description, config) VALUES
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'trading',
    '交易群',
    '接收交易信号和执行确认',
    '{"webhook": ""}'
),
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'alerts',
    '告警群',
    '接收风险预警和系统异常',
    '{"webhook": ""}'
),
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'reports',
    '报告群',
    '接收每日报告和周报',
    '{"webhook": ""}'
);

-- ============================================================================
-- DOWN Migration
-- ============================================================================

-- To rollback this migration:
-- DROP TABLE IF EXISTS notification_logs CASCADE;
-- DROP TABLE IF EXISTS notification_channels CASCADE;
-- DROP TABLE IF EXISTS notification_providers CASCADE;
