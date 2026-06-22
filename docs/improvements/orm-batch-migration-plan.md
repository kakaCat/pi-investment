# Repository 批量迁移到 ORM - 执行计划

## 🎯 目标

将剩余 22 个 Repository 从手动 SQL (psycopg2) 迁移到 SQLAlchemy ORM，确保：
- ✅ 每个 Repository 都有完整测试覆盖
- ✅ 每个 Repository 都经过代码审查
- ✅ 逐个迁移，分批验证，降低风险

## 📋 迁移清单（按优先级排序）

### 第一批：高频核心 Repository（今天完成）

| # | Repository | 表名 | 代码行数 | 优先级 | 状态 |
|---|-----------|------|---------|--------|------|
| 1 | ✅ kline_repository | klines | ~150 | ⭐⭐⭐ | 已完成 |
| 2 | ✅ strategy_repository | user_indicators | ~180 | ⭐⭐⭐ | 已完成 |
| 3 | backtest_repository | backtest_results | ~200 | ⭐⭐⭐ | 待迁移 |
| 4 | factor_repository | factors | ~150 | ⭐⭐⭐ | 待迁移 |
| 5 | stock_repository | stocks | ~120 | ⭐⭐⭐ | 待迁移 |

### 第二批：中频业务 Repository（明天完成）

| # | Repository | 表名 | 代码行数 | 优先级 | 状态 |
|---|-----------|------|---------|--------|------|
| 6 | signal_execution_repository | signal_executions | ~140 | ⭐⭐ | 待迁移 |
| 7 | portfolio_repository | portfolios | ~130 | ⭐⭐ | 待迁移 |
| 8 | position_repository | positions | ~110 | ⭐⭐ | 待迁移 |
| 9 | strategy_performance_repository | strategy_performance | ~90 | ⭐⭐ | 待迁移 |
| 10 | risk_repository | risk_configs | ~100 | ⭐⭐ | 待迁移 |

### 第三批：低频辅助 Repository（后天完成）

| # | Repository | 表名 | 代码行数 | 优先级 | 状态 |
|---|-----------|------|---------|--------|------|
| 11 | signal_execution_log_repository | signal_execution_logs | ~80 | ⭐ | 待迁移 |
| 12 | risk_config_repository | risk_configs | ~70 | ⭐ | 待迁移 |
| 13 | market_style_repository | market_styles | ~60 | ⭐ | 待迁移 |
| 14 | strategy_weight_repository | strategy_weights | ~50 | ⭐ | 待迁移 |
| 15 | strategy_circuit_breaker_repository | circuit_breakers | ~60 | ⭐ | 待迁移 |
| 16 | traceability_repository | traceability | ~70 | ⭐ | 待迁移 |
| 17 | ml_model_repository | ml_models | ~90 | ⭐ | 待迁移 |
| 18 | fund_flow_repository | fund_flows | ~80 | ⭐ | 待迁移 |

### 第四批：其他 Repository（后续）

剩余 6 个低频 Repository（根据实际需要迁移）

## 🔄 标准迁移流程（每个 Repository）

### 步骤 1: 阅读旧代码 + 设计 ORM 模型（5分钟）

```bash
# 1.1 阅读旧 Repository
Read quantsys-v2/repositories/xxx_repository.py

# 1.2 确认表结构（从数据库读取）
psql -h 127.0.0.1 -U mac -d quant_investment -c "\d table_name"

# 1.3 设计 ORM 模型（添加到 models.py）
# 或创建独立模型文件（如果表结构复杂）
```

**输出**：
- ORM 模型类定义
- 字段映射清单

### 步骤 2: 创建 V2 Repository（10分钟）

```bash
# 2.1 创建新文件
touch quantsys-v2/repositories/xxx_repository_v2.py

# 2.2 实现所有方法（使用 SQLAlchemy）
# 2.3 保持接口签名一致（参数和返回值）
# 2.4 添加向后兼容别名
```

**输出**：
- `xxx_repository_v2.py` 文件
- 所有方法实现完成

### 步骤 3: 编写测试用例（10分钟）

```bash
# 3.1 创建测试文件
touch quantsys-v2/tests/repositories/test_xxx_repository_v2.py

# 3.2 编写测试用例（至少覆盖）
# - CRUD 基本操作
# - 边界条件（空数据、无效参数）
# - 批量操作（如果有）
```

**测试模板**：
```python
import pytest
from repositories.xxx_repository_v2 import XXXRepositoryV2

class TestXXXRepositoryV2:
    def test_get_by_id(self):
        repo = XXXRepositoryV2()
        result = repo.get_by_id(1)
        # 断言

    def test_create(self):
        repo = XXXRepositoryV2()
        new_id = repo.create(...)
        assert new_id > 0

    def test_update(self):
        # ...

    def test_delete(self):
        # ...

    def test_list_with_filters(self):
        # ...
```

**输出**：
- 测试文件
- 至少 5 个测试用例

### 步骤 4: 运行测试 + 修复 Bug（5分钟）

```bash
# 4.1 运行单个测试文件
pytest tests/repositories/test_xxx_repository_v2.py -v

# 4.2 如果失败，修复代码
# 4.3 重新运行直到全部通过

# 4.4 检查覆盖率
pytest tests/repositories/test_xxx_repository_v2.py --cov=repositories.xxx_repository_v2
```

**通过标准**：
- ✅ 所有测试通过
- ✅ 覆盖率 > 80%

### 步骤 5: 代码审查（5分钟）

**审查清单**：

#### 5.1 功能正确性
- [ ] 所有旧方法都已实现
- [ ] 接口签名保持一致
- [ ] 返回值格式匹配（dict 结构）
- [ ] 异常处理正确

#### 5.2 ORM 最佳实践
- [ ] 使用 `get_db_session()` 上下文管理器
- [ ] 无手动 `cursor.close()`
- [ ] 无手动 `commit()`/`rollback()`
- [ ] 使用参数化查询（防止 SQL 注入）

#### 5.3 代码质量
- [ ] 无重复代码
- [ ] 变量命名清晰
- [ ] 添加必要的注释（复杂逻辑）
- [ ] 类型注解完整（参数和返回值）

#### 5.4 性能考虑
- [ ] 批量查询使用 `in_()` 而非循环
- [ ] 大数据量使用分页
- [ ] 避免 N+1 查询

**输出**：
- 审查报告（通过/需修改）
- 修改建议清单

### 步骤 6: 更新 Service 层引用（3分钟）

```bash
# 6.1 查找引用旧 Repository 的 Service
grep -r "from repositories.xxx_repository import" quantsys-v2/services/*.py

# 6.2 更新引用（逐个文件）
# 旧：from repositories.xxx_repository import XXXRepository
# 新：from repositories.xxx_repository_v2 import XXXRepositoryV2 as XXXRepository

# 6.3 运行相关测试
pytest tests/services/test_xxx_service.py -v
```

**输出**：
- Service 层引用已更新
- 集成测试通过

### 步骤 7: 对比测试（5分钟）

```bash
# 7.1 并行运行旧/新 Repository（可选）
# 对比返回结果是否一致

# 7.2 运行端到端测试
pytest tests/integration/ -v

# 7.3 手动冒烟测试（调用实际 API）
curl http://127.0.0.1:5001/api/xxx/test
```

**输出**：
- 新旧结果一致
- 端到端测试通过

### 步骤 8: 删除旧代码（2分钟）

```bash
# 8.1 确认无引用
grep -r "from repositories.xxx_repository import" quantsys-v2/ --exclude-dir=tests

# 8.2 删除旧文件
git rm quantsys-v2/repositories/xxx_repository.py

# 8.3 重命名 V2 文件（移除 _v2 后缀）
git mv repositories/xxx_repository_v2.py repositories/xxx_repository.py
```

**输出**：
- 旧代码已删除
- Git 提交记录清晰

## ⏱️ 时间估算

| 步骤 | 时间 | 说明 |
|------|------|------|
| 1. 阅读 + 设计 | 5 分钟 | 理解现有逻辑 |
| 2. 创建 V2 | 10 分钟 | 实现所有方法 |
| 3. 编写测试 | 10 分钟 | 至少 5 个用例 |
| 4. 运行测试 | 5 分钟 | 修复 Bug |
| 5. 代码审查 | 5 分钟 | 人工审查 |
| 6. 更新 Service | 3 分钟 | 更新引用 |
| 7. 对比测试 | 5 分钟 | 端到端验证 |
| 8. 删除旧代码 | 2 分钟 | 清理 |
| **总计** | **45 分钟/个** | 含测试和审查 |

**批量迁移时间**：
- 第一批（3个）：2-3 小时
- 第二批（5个）：3-4 小时
- 第三批（8个）：5-6 小时
- **总计**：10-13 小时（分 3 天完成）

## 🛡️ 风险控制

### 风险 1: 测试失败

**预防**：
- 先迁移简单的 Repository（少依赖）
- 每个 Repository 独立测试

**应对**：
- 立即回滚该 Repository
- 保留旧代码，V2 作为备选

### 风险 2: Service 层集成问题

**预防**：
- 保持接口签名一致
- 运行集成测试

**应对**：
- 使用向后兼容别名
- 渐进式切换（先少数 Service）

### 风险 3: 性能下降

**预防**：
- 使用 SQLAlchemy Core（性能接近原生）
- 批量查询优化

**应对**：
- 性能测试（对比旧/新）
- 慢查询优化（索引、分页）

## 📝 迁移报告模板

每个 Repository 迁移完成后，生成报告：

```markdown
# XXXRepository 迁移报告

## 基本信息
- Repository: xxx_repository
- 表名: xxx_table
- 代码行数: 旧 150 行 → 新 120 行
- 迁移时间: 2026-06-15 15:30

## 测试结果
- 测试用例: 8 个
- 通过率: 100%
- 覆盖率: 85%

## 代码审查
- 功能正确性: ✅ 通过
- ORM 最佳实践: ✅ 通过
- 代码质量: ✅ 通过
- 性能考虑: ✅ 通过

## 性能对比
- 查询速度: 1.2ms (旧) → 1.3ms (新) [+8%]
- 内存占用: 10MB (旧) → 8MB (新) [-20%]

## 遗留问题
- 无

## 审查人
- Claude (AI)

## 状态
✅ 已完成，已上线
```

## 🚀 立即开始

### 第一批（今天完成）

我将按照以下顺序迁移：

1. **backtest_repository** (最高优先级)
2. **factor_repository** (高频查询)
3. **stock_repository** (基础数据)

每个 Repository 完成后：
- 我会生成迁移报告
- 提交代码审查清单
- 等待你的确认后再继续下一个

准备好开始了吗？我先从 `backtest_repository` 开始！
