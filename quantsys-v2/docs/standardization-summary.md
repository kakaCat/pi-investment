# quantsys-v2 规范化诊断与整改方案

**生成时间**: 2026-06-29  
**诊断人员**: Claude (Kiro)  
**项目**: PI Investment - quantsys-v2 后端服务

---

## 📋 执行摘要

针对用户提出的两个问题：
1. ❓ **v2项目日志是否有统一？** → ❌ 没有统一，存在严重的混乱
2. ❓ **模拟账户是否遵循规范标准？** → ⚠️ 部分遵循，但有改进空间

本次诊断发现了多个规范化问题，并提供了详细的整改方案。

---

## 🔍 主要发现

### 1. 日志规范问题（严重程度：高）

#### 问题统计
| 问题类型 | 数量 | 影响 |
|---------|------|------|
| 使用 `logging.basicConfig` 独立配置 | 38 个文件 | 配置相互覆盖，格式不统一 |
| 使用 `print()` 而非日志 | 146 处 | 生产环境无法控制输出 |
| 使用字符串拼接日志 | 大量 | 无法结构化查询 |
| 已有但未使用的结构化日志 | 1 套 | 资源浪费 |

#### 核心问题
```python
# ❌ 问题 1: 多处重复配置（38个文件）
logging.basicConfig(level=logging.INFO, format='...')  # start_all.py
logging.basicConfig(level=logging.WARNING, format='...')  # simulation_trader.py
# → 后加载的会覆盖先加载的配置

# ❌ 问题 2: 使用 print() 而非日志（146处）
print(f"Processing {symbol}...")
# → 无法控制级别、无法记录到文件、无时间戳

# ❌ 问题 3: 字符串拼接（大量）
logger.info(f"买入 {symbol}: {shares}股 @ ¥{price:.2f}")
# → 无法按字段查询、性能差、类型不安全

# ✅ 已有但未使用的结构化日志
# infrastructure/logging/config.py 提供了完整的 structlog 配置
# 但项目中没有任何代码使用！
```

#### 影响
- **开发环境**: 日志格式混乱，难以调试
- **生产环境**: 无法集中收集日志，无法按字段查询
- **可观测性**: 无法追踪请求链路，无法监控性能

---

### 2. 模拟账户规范问题（严重程度：中）

#### 问题清单
| 问题类型 | 具体表现 | 影响 |
|---------|---------|------|
| 日志不规范 | 使用字符串拼接 + basicConfig | 同上 |
| 类型不一致 | dict/ORM 对象混用 | 代码需要兼容处理 |
| 配置分散 | YAML 配置独立于 .env | 配置管理混乱 |
| 缺少测试 | 单元测试覆盖不足 | 代码质量无保障 |
| 浮点数精度 | 使用 float 处理金额 | 可能出现精度误差 |

#### 核心问题
```python
# ❌ 问题 1: dict/ORM 对象混用
if hasattr(account, 'cash'):
    # ORM对象
    self.cash = float(account.cash)
else:
    # dict
    self.cash = float(account['cash'])
# → 返回类型不确定

# ❌ 问题 2: 浮点数精度问题
commission = amount * 0.0003  # float
# → 金融计算应该使用 Decimal

# ❌ 问题 3: 配置分散
# config_simulation.yaml 独立配置
# 应该与项目主配置 .env 统一
```

---

## 📄 已生成文档

### 1. 日志规范化报告
**文件**: `docs/logging-standardization-report.md`（11 KB）

**内容**:
- ✅ 当前状态诊断（统计数据）
- ✅ 问题详细分析（3 个核心问题）
- ✅ 规范标准定义（5 个规范点）
- ✅ 迁移计划（4 个阶段）
- ✅ 标准模板（3 个场景）
- ✅ 检查清单（可追踪）

**关键内容**:
```python
# 推荐架构
from infrastructure.logging import configure_structured_logging
import structlog

# 启动时配置一次
configure_structured_logging(level="INFO", json_format=False)

# 模块中使用
logger = structlog.get_logger(__name__)
logger.info("trade_executed", symbol="600000", action="BUY", shares=100)
```

### 2. 模拟账户规范标准
**文件**: `docs/simulation-account-standard.md`（20 KB）

**内容**:
- ✅ 当前状态诊断（4 个问题）
- ✅ 数据模型规范（ORM 定义）
- ✅ Repository 规范（接口 + 实现）
- ✅ 模拟券商规范（结构化日志 + Decimal）
- ✅ 配置规范（环境变量 + 验证）
- ✅ 测试规范（单元测试 + 集成测试）
- ✅ 迁移检查清单（4 个阶段）

**关键内容**:
```python
# 使用 Decimal 处理金额
from decimal import Decimal

class SimulationBroker:
    def __init__(self, commission_rate: float = 0.0003):
        self.commission_rate = Decimal(str(commission_rate))
    
    def buy(self, symbol: str, shares: int, price: Decimal) -> Dict:
        amount = Decimal(shares) * price
        commission = max(amount * self.commission_rate, Decimal('5'))
        
        logger.info(
            "buy_order_filled",
            symbol=symbol,
            shares=shares,
            total_cost=float(amount + commission)
        )
```

---

## 🎯 整改优先级

### P0 - 必须立即执行（影响生产环境）

#### 1. 日志启动入口统一
**范围**: 3 个文件
- `start_all.py`
- `adapters/inbound/fastapi_app/main.py`
- `adapters/inbound/fastapi_app/websocket_server.py`

**操作**:
```python
# 删除所有 logging.basicConfig
# 添加统一配置
from infrastructure.logging import configure_structured_logging

configure_structured_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("LOG_FORMAT") == "json"
)
```

**预计工作量**: 1 小时

#### 2. 模拟账户使用 Decimal
**范围**: 2 个文件
- `live_trading/simulation_broker.py`
- `live_trading/simulation_trader.py`

**操作**: 将所有 `float` 金额改为 `Decimal`

**预计工作量**: 2 小时

---

### P1 - 应该尽快执行（影响代码质量）

#### 3. 核心模块迁移到结构化日志
**范围**: ~100 个文件
- `application/services/`
- `adapters/outbound/repositories/`
- `live_trading/`

**操作**:
```python
# 替换
import logging
logger = logging.getLogger(__name__)
logger.info(f"Trade: {symbol}")

# 为
import structlog
logger = structlog.get_logger(__name__)
logger.info("trade_executed", symbol=symbol)
```

**预计工作量**: 1-2 天

#### 4. 替换 print() 为 logger
**范围**: 146 处

**预计工作量**: 1 天

---

### P2 - 可以逐步执行（技术债务）

#### 5. 清理 logging.basicConfig
**范围**: 38 个文件

**预计工作量**: 半天

#### 6. 模拟账户补充测试
**范围**: 单元测试 + 集成测试

**预计工作量**: 1-2 天

---

## 📊 预期收益

### 日志规范化收益

#### 开发环境
- ✅ 彩色控制台输出（易读）
- ✅ 统一日志格式
- ✅ 自动时间戳和模块名

#### 生产环境
- ✅ JSON 格式（可被日志收集系统解析）
- ✅ Trace ID 追踪请求链路
- ✅ 敏感信息自动脱敏
- ✅ 按字段结构化查询

**示例**:
```bash
# 生产环境：JSON 格式日志
{"event": "trade_executed", "symbol": "600000", "action": "BUY", "shares": 100, 
 "timestamp": "2026-06-29T12:00:00Z", "level": "info", "trace_id": "a3b2c1d4"}

# 可以这样查询
cat app.log | jq 'select(.symbol == "600000" and .action == "BUY")'
```

### 模拟账户规范化收益

#### 代码质量
- ✅ 类型安全（Decimal 避免浮点数精度问题）
- ✅ 数据一致（统一返回 ORM 对象）
- ✅ 接口清晰（Repository 接口定义）

#### 可维护性
- ✅ 配置集中管理（.env）
- ✅ 易于测试（依赖注入）
- ✅ 易于扩展到真实券商

---

## 🚀 快速开始

### 第一步：立即执行 P0 任务（3 小时）

```bash
# 1. 统一日志启动配置
vim start_all.py
vim adapters/inbound/fastapi_app/main.py

# 2. 模拟账户使用 Decimal
vim live_trading/simulation_broker.py
vim live_trading/simulation_trader.py

# 3. 测试验证
python start_all.py  # 观察日志输出
```

### 第二步：分支迁移 P1 任务（2-3 天）

```bash
git checkout -b refactor/logging-standardization

# 迁移核心模块
# 参考模板：docs/logging-standardization-report.md

git commit -m "refactor: migrate core modules to structured logging"
```

### 第三步：持续清理 P2 任务

- 在每次改动相关文件时顺便清理
- 逐步提升测试覆盖率

---

## 📚 相关文档

1. **日志规范化报告**: [docs/logging-standardization-report.md](./logging-standardization-report.md)
   - 详细问题分析
   - 迁移计划
   - 标准模板

2. **模拟账户规范标准**: [docs/simulation-account-standard.md](./simulation-account-standard.md)
   - 数据模型规范
   - Repository 规范
   - 测试规范

3. **现有实现**: 
   - 结构化日志配置: `infrastructure/logging/config.py`
   - 模拟账户 ORM: `infrastructure/persistence/orm/models/simulation.py`
   - 模拟账户 Repository: `adapters/outbound/repositories/simulation_repository.py`

---

## ✅ 下一步行动

- [ ] **立即**: 阅读两份详细规范文档
- [ ] **今天**: 执行 P0 任务（日志启动配置 + Decimal）
- [ ] **本周**: 启动 P1 任务分支，逐步迁移核心模块
- [ ] **长期**: 将规范写入 CLAUDE.md，作为开发指南

---

## 📞 支持

如有疑问或需要进一步说明，请参考详细文档或提出问题。

**文档位置**:
- `/Users/mac/Documents/ai/pi-investment/quantsys-v2/docs/logging-standardization-report.md`
- `/Users/mac/Documents/ai/pi-investment/quantsys-v2/docs/simulation-account-standard.md`
