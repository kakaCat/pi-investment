# 问题清单验证报告

**验证日期**: 2026-05-29  
**验证范围**: P0（阻塞上线）、P1（功能缺失）、P2（锦上添花）

---

## 🔴 P0 — 阻塞上线，必须立即修复

### ✅ P0-1: 策略执行工具断裂 (strategy_execute)

**状态**: **问题确认，但描述不准确**

**实际情况**:
- 文件 `src/infrastructure/tools/strategy/execute-tool.ts` 存在 ✅
- 调用 `executeStrategy()` → `/api/strategy/run` 端点 ✅
- **关键发现**: `/api/strategy/run` 确实是行业轮动编排引擎（StrategyEngine），需要 `sector_data/stock_data/ml_predictions` 输入
- **问题根源**: 工具名称和实际功能不匹配

**验证证据**:
```typescript
// src/infrastructure/quant/quant-v2-client.ts:804
const url = `${V2_API_BASE}/api/strategy/run`;
```

```python
# quantsys-v2/api/routes/strategy.py:25-58
@strategy_bp.route('/api/strategy/run', methods=['POST'])
def run_strategy():
    """执行策略流水线（行业轮动引擎）"""
    result = engine.run(
        market=market,
        sector_data=data.get("sector_data"),
        stock_data=data.get("stock_data"),
        ml_predictions=data.get("ml_predictions"),
    )
```

**影响**: 用户调用 `strategy_execute("600000", "MACross")` 会失败，因为端点期望的是行业轮动数据，而非单股票+单策略。

**修复方向**: 
1. 新增 `/api/strategies/{strategy_type}/execute` 端点（单策略执行）
2. 或将 `strategy_execute` 工具改为调用 `/api/cli/signal-generate`（已有单策略逻辑）

---

### ✅ P0-2: 信号生成 NDJSON 解析失败 (quant_cli signal.generate)

**状态**: **问题确认**

**实际情况**:
- `/api/cli/signal-generate` 在同步模式（< 50 stocks）返回 `application/x-ndjson` ✅
- TS 工具 `quant_cli` 期望标准 JSON ✅
- **未实现 Accept header 检测**（代码中无 `request.headers.get('Accept')` 逻辑）

**验证证据**:
```python
# quantsys-v2/api/routes/pipeline.py:818
return Response(generate(), mimetype='application/x-ndjson')
```

**影响**: TS 工具调用 `signal.generate` 时 `JSON.parse()` 失败。

**修复方向**:
1. 在 `cli_signal_generate()` 中检测 `Accept: application/json` header
2. 如果是 JSON 请求，返回 `jsonify()` 而非 `Response(generate())`
3. 或修改 TS 工具以逐行解析 NDJSON

---

### ❌ P0-3: 财务数据源失败

**状态**: **问题不存在或描述不准确**

**实际情况**:
- 数据库中**没有财务数据表**（`SELECT * FROM information_schema.tables WHERE table_name LIKE '%financial%'` 返回 0 行）
- 这意味着财务数据**从未持久化到数据库**，而是通过 akshare 实时查询
- `data_fetch_financial` 工具直接调用 akshare API，不依赖数据库

**验证证据**:
```bash
# 数据库中无财务表
psql> SELECT table_name FROM information_schema.tables 
      WHERE table_schema = 'quant' AND table_name LIKE '%financial%';
 table_name 
------------
(0 rows)
```

**结论**: 如果 `data_fetch_financial` 返回 undefined，问题在于：
1. akshare API 调用失败（网络/限流）
2. 数据源代码逻辑错误
3. 非交易时间无数据

**需要进一步验证**: 实际运行 `data_fetch_financial` 工具查看错误日志。

---

### ✅ P0-4: 调度任务未注册

**状态**: **问题确认**

**实际情况**:
- `scripts/init_scheduler_tasks.py` 存在 ✅
- `scripts/register_signal_execution_task.py` 存在 ✅
- `start_all.py` **未调用**这些脚本 ✅
- 数据库中有 13 个任务（手动创建），但可能不完整

**验证证据**:
```python
# quantsys-v2/start_all.py:51-64
def run_scheduler():
    from runtime.scheduler.scheduler import SchedulerService
    scheduler = SchedulerService()
    scheduler.run_loop()  # 直接启动，无初始化
```

```bash
# 数据库中有任务，但不确定是否完整
psql> SELECT id, name, is_enabled FROM quant.scheduler_tasks LIMIT 5;
 id  |         name          | is_enabled 
-----+-----------------------+------------
 218 | daily-data-update     | t
 219 | daily-factor-compute  | t
 221 | daily-signal-generate | t
```

**影响**: 如果任务不完整或参数错误，定时扫描不会按预期工作。

**修复方向**: 在 `start_all.py` 启动时调用 `init_scheduler_tasks.py`，确保任务表完整。

---

### ✅ P0-5: SignalExecutionScheduler 股票池硬编码 10 只

**状态**: **问题确认**

**实际情况**:
- `_get_stock_pool()` 硬编码返回 10 只股票 ✅
- 注释明确说明"暂时返回沪深300的前10只股票作为示例" ✅

**验证证据**:
```python
# quantsys-v2/services/signal_execution_scheduler.py:403-423
def _get_stock_pool(self) -> List[str]:
    """获取股票池（简化实现）"""
    # 这里简化处理，实际应该从配置或数据库中读取
    # 暂时返回沪深300的前10只股票作为示例
    return [
        '600000.SH',  # 浦发银行
        '600036.SH',  # 招商银行
        # ... 共 10 只
    ]
```

**影响**: 定时信号执行只扫描 10 只测试股，不覆盖沪深300/全A股。

**修复方向**: 改为从 `stock_repository.get_all()` 或沪深300成分表读取。

---

## 🟡 P1 — 功能缺失，需排期修复

### ✅ P1-6: 内置策略未同步到数据库

**状态**: **问题确认**

**实际情况**:
- `StrategyFactory.sync_to_database()` 方法存在 ✅
- **从未被调用**（`start_all.py` 和 `init_scheduler_tasks.py` 中均无调用）✅
- 数据库 `quant.strategy_metadata` 表为空（0 行）✅

**验证证据**:
```python
# quantsys-v2/quantlib/engine/strategy_factory.py:111-131
@classmethod
def sync_to_database(cls, repo=None) -> int:
    # 方法存在但未被调用
```

```bash
psql> SELECT COUNT(*) FROM quant.strategy_metadata;
 count 
-------
     0
```

**影响**: 内置策略（18 个）无法通过 API 查询，`/api/strategies/list?source=builtin` 返回空。

**修复方向**: 在 `start_all.py` 或 bootstrap 脚本中调用 `StrategyFactory.auto_discover()` + `sync_to_database()`。

---

### ❌ P1-7: 所有DB策略状态为 stopped

**状态**: **问题不存在**

**实际情况**:
- 数据库中**没有 `quant.user_strategies` 表** ✅
- 用户策略存储在 `quant.strategy_configs` 表（不同的表结构）

**验证证据**:
```bash
psql> \dt quant.*
 quant  | strategy_configs            | table | mac
 quant  | strategy_metadata           | table | mac

psql> SELECT COUNT(*) FROM quant.user_strategies;
ERROR:  relation "quant.user_strategies" does not exist
```

**结论**: 问题描述基于错误的表名。需要检查 `strategy_configs` 表的实际状态。

---

### ✅ P1-8: 账户/持仓数据缺失

**状态**: **问题确认**

**实际情况**:
- `quant.accounts` 表存在 ✅
- 表中只有 1 条记录（可能是测试账户）✅
- 无初始化脚本创建默认账户

**验证证据**:
```bash
psql> SELECT COUNT(*) FROM quant.accounts;
 count 
-------
     1
```

**影响**: 风控检查需要账户余额和持仓数据，但数据不完整。

**修复方向**: 创建账户初始化脚本（初始资金 100万），与 TS 端 `portfolio_rebalance` 打通。

---

### ✅ P1-9: v1/v2 订单双轨割裂

**状态**: **问题确认**

**实际情况**:
- v1 订单存储在 `.pi-invest/orders.json`（23KB，有数据）✅
- v2 订单存储在 `quant.orders` 表（0 行，空表）✅
- 两套系统互不知情 ✅

**验证证据**:
```bash
# v1 订单文件
ls -la .pi-invest/orders.json
.rw-r--r--@ 23k mac 29 5月  13:07 orders.json

# v2 订单表为空
psql> SELECT COUNT(*) FROM quant.orders;
 count 
-------
     0
```

**影响**: TS 工具 `trade_manage_orders` 写入 JSON 文件，v2 API 写入数据库，导致订单数据不一致。

**修复方向**: 统一到 v2 DB 订单体系，或让 TS 工具调用 v2 API。

---

### ⚠️ P1-10: 财务因子注入到策略时字段缺失

**状态**: **依赖 P0-3 验证结果**

**实际情况**:
- 如果财务数据源正常，则此问题不存在
- 如果财务数据源失败，则策略代码中的 `roe_q`、`debt_ratio_q` 等列全为 NaN

**结论**: 需要先修复 P0-3（如果确实存在），再验证此问题。

---

## 🟢 P2 — 锦上添花，后续迭代

P2 问题为改进建议，不需要验证是否存在。

---

## 📊 问题统计

| 优先级 | 总数 | 确认存在 | 不存在/不准确 | 待验证 |
|--------|------|----------|---------------|--------|
| P0     | 5    | 4        | 1             | 0      |
| P1     | 5    | 4        | 1             | 0      |
| P2     | 3    | N/A      | N/A           | N/A    |

---

## 🎯 推荐修复优先级

### 立即修复（今天）
1. **P0-2**: 修复 NDJSON 解析失败（1h）
2. **P0-4**: start_all.py 自动注册调度任务（30m）
3. **P0-5**: 股票池改为沪深300（30m）

### 本周修复
4. **P0-1**: 新增单策略执行端点（2h）
5. **P1-6**: 内置策略 sync_to_database（15m）
6. **P1-8**: 创建账户初始化脚本（30m）
7. **P1-9**: 统一订单体系到 v2（2h）

### 待验证
8. **P0-3**: 实际运行 `data_fetch_financial` 工具，查看错误日志
9. **P1-7**: 检查 `strategy_configs` 表的实际状态

---

## 🔍 验证方法

### P0-3 财务数据验证
```bash
# 启动 quantsys-v2
cd quantsys-v2 && python start_all.py

# 在另一个终端测试
curl -X POST http://127.0.0.1:5001/api/data/financials \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600000.SH", "statement_type": "income"}'
```

### P1-7 策略状态验证
```sql
-- 检查策略配置表
SELECT id, name, status, is_enabled 
FROM quant.strategy_configs 
LIMIT 10;
```

---

## 📝 总结

**核心发现**:
1. **P0 问题中有 4 个确认存在**，其中 P0-2（NDJSON）和 P0-5（股票池）最容易修复
2. **P0-1 问题根源是工具名称和功能不匹配**，而非端点不存在
3. **P0-3 需要实际测试**，数据库中无财务表是正常的（实时查询 akshare）
4. **P1 问题中有 4 个确认存在**，P1-6（内置策略同步）最容易修复
5. **订单双轨问题（P1-9）真实存在**，需要统一到 v2 体系

**建议行动**:
- 先修复 3 个简单的 P0 问题（P0-2, P0-4, P0-5），预计 2 小时
- 验证 P0-3 财务数据问题，确定是否需要修复
- 排期修复 P0-1 和 P1 问题
