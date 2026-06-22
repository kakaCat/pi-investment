# ORM 批量迁移进度报告

## 📊 当前进度

**已完成**: 5/24 (20.8%)
**剩余**: 19/24 (79.2%)

### ✅ 已完成迁移

| # | Repository | 状态 | 测试 | 行数 | 耗时 |
|---|-----------|------|------|------|------|
| 1 | kline_repository | ✅ 完成 | 20/20 | 220行 | 30分钟 |
| 2 | strategy_repository | ✅ 完成 | 21/21 | 250行 | 30分钟 |
| 3 | backtest_repository | ✅ 完成 | 20/20 | 370行 | 45分钟 |
| 4 | factor_repository | ✅ 完成 | 17/17 | 400行 | 30分钟 |
| 5 | stock_repository | ✅ 完成 | 23/23 | 380行 | 40分钟 |

**总计**: 5 个 Repository，1620 行代码，101 个测试用例，~2.75 小时

### ⏳ 待迁移（按优先级）

#### 第一批：高频核心 ✅ 全部完成！

#### 第二批：中频业务（5 个）
- [ ] signal_execution_repository
- [ ] portfolio_repository
- [ ] position_repository
- [ ] strategy_performance_repository
- [ ] risk_repository

#### 第三批：低频辅助（8 个）
- [ ] signal_execution_log_repository
- [ ] risk_config_repository
- [ ] market_style_repository
- [ ] strategy_weight_repository
- [ ] strategy_circuit_breaker_repository
- [ ] traceability_repository
- [ ] ml_model_repository
- [ ] fund_flow_repository

#### 第四批：其他（6 个）
- [ ] signal_repository
- [ ] order_repository
- [ ] trade_repository
- [ ] financial_repository
- [ ] indicator_repository
- [ ] model_repository

## 🎯 完成标准

每个 Repository 迁移需要：

### 1. 代码实现 ✅
- [ ] 创建 `xxx_repository_v2.py`
- [ ] 所有方法已实现
- [ ] 使用 `get_db_session()` 上下文管理器
- [ ] 使用 `text()` + 命名参数（防止 SQL 注入）
- [ ] 向后兼容别名

### 2. 测试覆盖 ✅
- [ ] 创建 `test_xxx_repository_v2.py`
- [ ] 至少 5 个测试用例
- [ ] 覆盖主要方法（CRUD）
- [ ] 测试通过率 100%

### 3. 代码审查 ✅
- [ ] 功能正确性
- [ ] ORM 最佳实践
- [ ] 代码质量
- [ ] 性能考虑

### 4. 集成验证 ✅
- [ ] 更新 Service 层引用
- [ ] 运行集成测试
- [ ] 删除旧代码

### 5. 文档记录 ✅
- [ ] 生成迁移报告
- [ ] 记录遇到的问题和解决方案

## 📝 迁移模板

### 标准化流程（每个 ~45 分钟）

```bash
# 1. 创建 V2 Repository（15 分钟）
# - 读取旧代码
# - 查看表结构
# - 实现所有方法
# - 添加向后兼容

# 2. 编写测试用例（10 分钟）
# - 基础 CRUD 测试
# - 边界条件测试
# - 批量操作测试

# 3. 运行测试并修复（10 分钟）
cd quantsys-v2
python -m pytest tests/repositories/test_xxx_repository_v2.py -v

# 4. 代码审查（5 分钟）
# - 检查 SQL 语法
# - 检查字段匹配
# - 检查可选字段默认值

# 5. 生成报告（5 分钟）
# - 记录测试结果
# - 记录遇到的问题
# - 记录性能对比
```

### 常见问题和解决方案

#### 问题 1: SQL 参数占位符错误
```python
# ❌ 错误
:name::jsonb

# ✅ 修复
CAST(:name AS jsonb)
```

#### 问题 2: 表字段不匹配
```bash
# 解决方案：先查看表结构
psql -h 127.0.0.1 -U mac -d quant_investment -c "\d table_name"
```

#### 问题 3: 可选字段缺失
```python
# 解决方案：为所有可选字段设置默认值
for field in ['optional_field1', 'optional_field2']:
    if field not in data:
        data[field] = None
```

#### 问题 4: JSONB 字段处理
```python
# 转换为 JSON 字符串
if isinstance(data['jsonb_field'], (dict, list)):
    data['jsonb_field'] = json.dumps(data['jsonb_field'])

# SQL 中使用 CAST
CAST(:jsonb_field AS jsonb)
```

## 🚀 快速继续指南

### 立即开始（今天完成剩余高频 Repository）

```bash
# 1. Factor Repository 测试
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 创建测试文件
touch tests/repositories/test_factor_repository_v2.py

# 编写测试（参考 test_backtest_repository_v2.py）
# 运行测试
python -m pytest tests/repositories/test_factor_repository_v2.py -v

# 2. Stock Repository 迁移
# 按照相同流程迁移 stock_repository
```

### 批量迁移脚本（可选）

```bash
# 使用自动化脚本辅助
python scripts/batch_migrate_repositories.py --list
python scripts/batch_migrate_repositories.py --batch 1
```

### 更新 Service 层（迁移完成后）

```bash
# 查找所有引用旧 Repository 的文件
grep -r "from repositories\." quantsys-v2/services/*.py | grep -v "_v2"

# 批量替换
sed -i '' 's/from repositories.xxx_repository import/from repositories.xxx_repository_v2 import/g' quantsys-v2/services/*.py
```

## 📈 预计剩余时间

| 批次 | Repository 数 | 预计时间 | 建议时间 |
|------|--------------|---------|---------|
| 第一批（高频核心） | 5 | ✅ 已完成 | ✅ 2.75 小时 |
| 第二批（中频业务） | 5 | 3-4 小时 | 明天完成 |
| 第三批（低频辅助） | 8 | 5-6 小时 | 后天完成 |
| 第四批（其他） | 6 | 4-5 小时 | 按需完成 |
| **总计** | **24** | **15-18 小时** | **3-4 天** |
| **已完成** | **5 (20.8%)** | **2.75 小时** | **✅** |

## ✅ 完成后清单

- [ ] 所有 24 个 Repository 已迁移
- [ ] 所有测试通过（预计 200+ 测试用例）
- [ ] Service 层引用已更新（29 个文件）
- [ ] 集成测试通过
- [ ] 旧 Repository 代码已删除
- [ ] 手写连接池代码已删除
- [ ] 更新 `__init__.py` 导出
- [ ] 更新文档

## 🎉 预期收益

### 立即收益
- ✅ 连接泄漏归零（19 idle → 5-10）
- ✅ 代码量减少 ~60%
- ✅ 类型安全（IDE 支持）
- ✅ SQL 注入防护

### 长期收益
- ✅ 维护成本降低
- ✅ 代码可读性提升
- ✅ 异步支持（未来）
- ✅ 测试覆盖率提升

## 📚 参考资料

### 已完成的迁移报告
- `docs/improvements/backtest-repository-migration-report.md`
- `docs/improvements/sqlalchemy-orm-completion-report.md`
- `docs/improvements/orm-migration-design.md`

### 迁移计划
- `docs/improvements/orm-batch-migration-plan.md`
- `docs/improvements/connection-pool-vs-orm-comparison.md`

### 自动化脚本
- `scripts/batch_migrate_repositories.py`

---

**当前状态**: 已完成 4/24 Repository，累计 2 小时工作量。建议继续按批次完成剩余 20 个 Repository。

**下一步**: 完成 factor_repository 测试，然后继续 stock_repository。
