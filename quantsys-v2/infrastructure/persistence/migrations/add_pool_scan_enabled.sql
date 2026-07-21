"""
数据库迁移脚本：为股票池添加扫描开关

功能：为 stock_pools 表添加 scan_enabled 字段
"""

-- 1. 添加 scan_enabled 字段（默认开启）
ALTER TABLE quant.stock_pools
ADD COLUMN IF NOT EXISTS scan_enabled BOOLEAN DEFAULT true;

-- 2. 添加字段注释
COMMENT ON COLUMN quant.stock_pools.scan_enabled IS '是否启用每日扫描（true=启用，false=禁用）';

-- 3. 为现有股票池启用扫描
UPDATE quant.stock_pools
SET scan_enabled = true
WHERE scan_enabled IS NULL;

-- 4. 查看结果
SELECT id, name, pool_type, scan_enabled, created_at
FROM quant.stock_pools
ORDER BY id;
