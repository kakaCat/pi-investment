-- 009_backfill_stocks_sector.sql
-- 从 industry 顶层类目回填 sector 列（industry 形如「制造业-通用设备制造业」）
-- 2026-07-28 前 sector 列从未被任何代码写入，sector_analysis 全落「未分类」
UPDATE quant.stocks
SET sector = split_part(industry, '-', 1)
WHERE (sector IS NULL OR sector = '')
  AND industry IS NOT NULL
  AND industry <> '';
