# 数据迁移与回滚

> REQ-260925212722-96e7: REQ 流水线 Dive 模式重构

## 数据库变更 «serves: FR-1»

### 变更内容 «serves: FR-1»

**表**: `requirements`

**新增列**: `dive` (JSONB, nullable)

### 迁移脚本 «serves: FR-1»

**位置**: `migrations/YYYYMMDDHHMMSS_add_dive_to_requirements.sql`

**内容**:
```sql
-- Up Migration
ALTER TABLE requirements 
ADD COLUMN dive JSONB DEFAULT NULL;

-- 创建索引（用于查询 armed 的需求）
CREATE INDEX idx_requirements_dive_activation 
ON requirements ((dive->>'activation'));

-- 创建索引（用于查询 active 的需求）
CREATE INDEX idx_requirements_dive_phase 
ON requirements ((dive->>'phase'));

-- 添加注释
COMMENT ON COLUMN requirements.dive IS 'Dive 自动续跑状态（可选，老需求为 null）';
```

### 回滚脚本 «serves: FR-1»

```sql
-- Down Migration
DROP INDEX IF EXISTS idx_requirements_dive_activation;
DROP INDEX IF EXISTS idx_requirements_dive_phase;

ALTER TABLE requirements 
DROP COLUMN IF EXISTS dive;
```

## 数据兼容性 «serves: FR-1, FR-7»

### 向后兼容 «serves: FR-1»

- **老需求**: `dive = null` → 手动模式
- **新需求**: `dive = { ... }` → 自动模式（可选启用）
- **不需要数据迁移**: 添加的是可选列，默认值为 null

### 验证方法 «serves: FR-1»

**检查列存在**:
```sql
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'requirements' AND column_name = 'dive';
```

**预期结果**:
```
column_name | data_type | is_nullable
-----------------------------------------
dive        | jsonb     | YES
```

**检查索引存在**:
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'requirements' 
  AND indexname LIKE 'idx_requirements_dive%';
```

**预期结果**:
```
indexname                         | indexdef
--------------------------------------------------------------------------------
idx_requirements_dive_activation  | CREATE INDEX ... ((dive->>'activation'))
idx_requirements_dive_phase       | CREATE INDEX ... ((dive->>'phase'))
```

## 迁移步骤 «serves: FR-1»

### 正向迁移 «serves: FR-1»

1. **备份数据库**:
```bash
pg_dump -h localhost -U postgres -d quant_investment > backup_before_dive.sql
```

2. **执行迁移**:
```bash
psql -h localhost -U postgres -d quant_investment < migrations/YYYYMMDDHHMMSS_add_dive_to_requirements.sql
```

3. **验证迁移**:
```sql
-- 检查列存在
SELECT EXISTS (
  SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'requirements' AND column_name = 'dive'
);

-- 检查索引存在
SELECT count(*) FROM pg_indexes 
WHERE tablename = 'requirements' 
  AND indexname LIKE 'idx_requirements_dive%';
```

**预期结果**: 列存在返回 `true`，索引数量返回 `2`

4. **测试兼容性**:
```sql
-- 查询老需求（dive = null）
SELECT id, title, dive FROM requirements WHERE dive IS NULL LIMIT 5;

-- 创建测试需求
INSERT INTO requirements (id, title, category, status, dive) 
VALUES (
  'REQ-test-dive',
  'Test Dive',
  'feature',
  'brainstorming',
  '{"phase": "active", "activation": "armed", "currentStage": "brainstorming", "stagesCompleted": [], "roundsInStage": 0, "maxRoundsPerStage": 5, "createdAt": 1695648000000, "updatedAt": 1695648000000}'::jsonb
);

-- 查询测试需求
SELECT id, dive->>'phase', dive->>'activation' 
FROM requirements 
WHERE id = 'REQ-test-dive';

-- 清理测试数据
DELETE FROM requirements WHERE id = 'REQ-test-dive';
```

### 回滚步骤 «serves: FR-1»

1. **确认回滚意图**:
```bash
# 检查是否有需求使用了 dive 字段
psql -h localhost -U postgres -d quant_investment -c   "SELECT count(*) FROM requirements WHERE dive IS NOT NULL;"
```

**警告**: 如果有需求使用了 dive 字段，回滚将丢失这些数据！

2. **备份当前数据**:
```bash
pg_dump -h localhost -U postgres -d quant_investment > backup_before_rollback.sql
```

3. **执行回滚**:
```bash
psql -h localhost -U postgres -d quant_investment -c "
  DROP INDEX IF EXISTS idx_requirements_dive_activation;
  DROP INDEX IF EXISTS idx_requirements_dive_phase;
  ALTER TABLE requirements DROP COLUMN IF EXISTS dive;
"
```

4. **验证回滚**:
```sql
-- 检查列已删除
SELECT EXISTS (
  SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'requirements' AND column_name = 'dive'
);
```

**预期结果**: 返回 `false`

## 风险评估 «serves: FR-1, FR-2»

### 迁移风险 «serves: FR-1»

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|----------|
| 迁移失败 | 低 | 数据库锁定 | 备份数据库，在低峰期执行 |
| 索引创建慢 | 低 | 短暂性能下降 | 并发创建索引（CONCURRENTLY） |
| 数据丢失 | 无 | 无影响 | 添加的是新列，不修改现有数据 |

### 回滚风险 «serves: FR-1»

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据丢失 | 中 | dive 数据丢失 | 回滚前备份，确认无需求使用 dive |
| 应用兼容性 | 低 | 老代码仍能运行 | dive 字段是可选的 |

## 性能影响 «serves: FR-2»

### 存储影响 «serves: FR-1»

- **每个需求**: 约 200-300 字节（JSONB）
- **10000 个需求**: 约 2-3 MB
- **影响**: 可忽略

### 查询性能 «serves: FR-2»

- **无索引查询**: O(n) 全表扫描
- **有索引查询**: O(log n) 索引扫描
- **索引开销**: 每个索引约 1-2 MB（10000 条记录）

### 优化建议 «serves: FR-2»

- 使用索引查询 armed 需求: `WHERE dive->>'activation' = 'armed'`
- 使用索引查询 active 需求: `WHERE dive->>'phase' = 'active'`
- 避免全表扫描 JSONB 字段

## 监控指标 «serves: FR-2»

### 迁移后监控 «serves: FR-2»

- **dive 字段使用率**: `SELECT count(*) FROM requirements WHERE dive IS NOT NULL`
- **armed 需求数量**: `SELECT count(*) FROM requirements WHERE dive->>'activation' = 'armed'`
- **索引命中率**: 检查 pg_stat_user_indexes
- **JSONB 存储大小**: `SELECT pg_column_size(dive) FROM requirements WHERE dive IS NOT NULL`

### 告警阈值 «serves: FR-2»

- armed 需求数 > 100: 可能有问题，需要检查
- dive 字段平均大小 > 1KB: 数据结构可能过于复杂
- 索引未使用（idx_scan = 0）: 考虑删除索引