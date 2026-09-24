---
requirement_refs: [FR-3]
---

# 迁移方案（REQ-example）

## 迁移步骤 <!-- serves: FR-3 -->

| 编号 | 操作（可复制粘贴的命令） | 验证（跑什么看到什么算过） | 失败回滚（完整命令） |
|---|---|---|---|
| M-1 | `mysql -u root -p < migrations/001_add_kind_column.sql` | `mysql -e "DESCRIBE artifacts" | grep kind` → 输出包含 kind 列 | `mysql -u root -p < migrations/001_rollback.sql` |
| M-2 | `node scripts/backfill_kind.js --dry-run` | 输出 "affected rows: 1000, all template_key non-null" | 无需回滚（只读操作） |
| M-3 | `node scripts/backfill_kind.js` | `mysql -e "SELECT COUNT(*) FROM artifacts WHERE kind IS NULL"` → 输出 0 | `mysql -e "UPDATE artifacts SET kind=NULL WHERE updated_at > '2026-01-15'"` |

## 影响评估 <!-- serves: FR-3 -->

- **影响范围**：artifacts 表（新增 kind 列）、POST /api/requirements/:id/artifacts 接口（必须传 kind）
- **停机窗口**：不需要完全停机，M-3 执行期间（30 秒）只读模式
- **停机时段**：凌晨 2:00-2:30（业务低峰）
- **用户感知**：迁移期间新建需求的模板生成暂时不可用（弹窗提示"系统维护中"）

## 回滚路径 <!-- serves: FR-3 -->

**回滚触发条件**（任一满足即回滚）：
1. M-3 执行后 5 分钟内，错误日志 "kind constraint violation" > 10 次
2. 监控显示 kind=NULL 行数 > 100（回填失败）
3. 用户投诉"新建需求后看不到文档" > 3 人

**回滚步骤**：
```bash
# 1. 回滚数据
mysql -u root -p < migrations/001_rollback_data.sql

# 2. 回滚代码
git checkout v1.2.3
./deploy.sh --skip-migration
```

**回滚后状态**：
- kind 列仍存在但全为 NULL（列保留，数据清空）
- 旧版本接口不要求 kind 字段（兼容模式）
- 产物清单筛选功能不可用（按 kind 筛选的按钮置灰）
