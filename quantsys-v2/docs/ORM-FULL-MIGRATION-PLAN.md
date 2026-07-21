# ORM完全迁移执行计划

## ⚠️ 重要提醒

这是一个**破坏性变更**，将：
1. 删除所有原生SQL Repository
2. 修改所有调用方代码使用ORM
3. 不可快速回滚

## 执行前检查清单

- [ ] 已备份代码（git commit）
- [ ] 已通过所有ORM测试
- [ ] 已在开发环境验证
- [ ] 团队已知晓变更

## 迁移步骤

### 阶段1: 备份和准备（必须）

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 1. 提交当前所有ORM新增文件
git add infrastructure/persistence/orm/
git add adapters/outbound/repositories/orm/
git add application/services/data_service_orm.py
git add application/services/data_service_adaptive.py
git add adapters/outbound/repositories/factory.py
git add docs/orm-*.md
git add scripts/test_orm*.py
git add scripts/comprehensive_review.py
git add scripts/demo_orm_features.py

git commit -m "feat: 添加ORM基础设施和核心Repository（阶段1完成）"

# 2. 创建迁移分支
git checkout -b orm-full-migration
```

### 阶段2: 删除原生SQL Repository（22个待迁移+7个已有ORM版本）

**已有ORM版本，可安全删除**：
```bash
rm adapters/outbound/repositories/stock_repository.py
rm adapters/outbound/repositories/kline_repository.py
rm adapters/outbound/repositories/signal_repository.py
rm adapters/outbound/repositories/portfolio_repository.py
rm adapters/outbound/repositories/factor_repository.py
rm adapters/outbound/repositories/backtest_repository.py
rm live_trading/simulation_repository.py  # SimulationORMRepository已实现
```

**未实现ORM版本，需要先创建或删除**：
- async_kline_repository.py
- signal_execution_repository.py
- risk_repository.py
- strategy_repository.py
- strategy_performance_repository.py
- financial_repository.py
- risk_config_repository.py
- order_repository.py
- ... 其他15个

### 阶段3: 修改所有调用方

**需要修改的模块**：
1. application/services/ (所有Service)
2. jobs/ (所有Job)
3. api/ (所有API)
4. live_trading/ (交易模块)
5. backtest/ (回测模块)
6. tests/ (所有测试)

**修改模式**：
```python
# 修改前
from adapters.outbound.repositories.stock_repository import StockRepository
repo = StockRepository()

# 修改后
from adapters.outbound.repositories.orm import StockORMRepository
from infrastructure.persistence.orm import close_session

repo = StockORMRepository()
try:
    # ... 业务逻辑
finally:
    close_session()
```

### 阶段4: 更新初始化代码

**需要在应用启动时初始化ORM**：
```python
# 在main.py或app.py中
from infrastructure.persistence.orm import init_orm

# 应用启动时
init_orm()

# Flask/FastAPI中添加清理
@app.teardown_appcontext
def cleanup(exception=None):
    from infrastructure.persistence.orm import close_session
    close_session()
```

### 阶段5: 删除Feature Flag（不再需要切换）

```bash
rm adapters/outbound/repositories/factory.py
rm application/services/data_service_adaptive.py
```

直接使用：
```python
# data_service.py 改为直接使用ORM
from application.services.data_service_orm import DataServiceORM as DataService
```

### 阶段6: 测试验证

```bash
# 运行所有ORM测试
python scripts/test_orm.py
python scripts/test_orm_repositories.py
python scripts/test_orm_batch2.py
python scripts/comprehensive_review.py

# 运行原有测试（需要先修改测试代码）
pytest tests/
```

### 阶段7: 提交变更

```bash
git add .
git commit -m "feat: 完全迁移到ORM架构，删除原生SQL代码

BREAKING CHANGE: 
- 删除所有原生SQL Repository
- 所有代码改用SQLAlchemy ORM
- 应用启动需要调用init_orm()
- 请求结束需要调用close_session()
"
```

## 预计工作量

| 任务 | 文件数 | 预计时间 |
|------|--------|----------|
| 创建剩余Repository | 22个 | 3-4小时 |
| 修改Service层 | ~10个 | 1小时 |
| 修改Job | ~20个 | 2小时 |
| 修改API | ~15个 | 1.5小时 |
| 修改测试 | ~50个 | 3小时 |
| 验证测试 | 全部 | 2小时 |
| **总计** | **~117个** | **12-13小时** |

## 风险评估

### 高风险项
1. ⚠️ 批量操作性能可能下降
2. ⚠️ 某些复杂SQL可能难以用ORM表达
3. ⚠️ 测试覆盖可能不完整

### 缓解措施
1. 保留git历史，可回滚
2. 复杂SQL使用session.execute()
3. 充分测试后再部署

## 建议

**鉴于工作量巨大（~12小时，117个文件），建议：**

### 方案A：渐进式迁移（推荐）✅
1. 保留原生SQL Repository作为后备
2. 新功能使用ORM
3. 旧代码按需迁移
4. 用Feature Flag控制切换

**优点**：安全、可回滚、风险低
**缺点**：双轨并行，维护成本高

### 方案B：完全迁移（激进）⚠️
1. 创建剩余22个ORM Repository
2. 修改所有调用方（~117个文件）
3. 删除原生SQL代码
4. 全面测试

**优点**：彻底、干净
**缺点**：工作量大、风险高、不可快速回滚

## 你的选择？

请确认是否要执行**方案B：完全迁移**？

如果确认，我会：
1. ✅ 先创建剩余22个ORM Repository
2. ✅ 然后逐步修改调用方代码
3. ✅ 最后删除原生SQL代码

**这将是一个大规模重构，请慎重决定！**

是否继续？
