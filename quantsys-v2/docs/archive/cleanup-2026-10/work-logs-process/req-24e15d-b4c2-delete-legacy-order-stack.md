# REQ-24e15d B4-c2：legacy 订单栈彻底删除（A 方案）

- 日期：2026-09-14
- 窗口：w-32314d00（投资脑 investor）
- 前置：B4-c1（`54830404` / `6d65435b`）
- 授权：用户明示「A. 删除」

## 一句话结论

B4-c1 判定为「对着不存在的表写 SQL」的 legacy 订单栈，本批按 A 方案整体删除。
**过程中发现并修好了一条静默失效的调度链**——它已经三周没有真正下过单。

## 一、删除清单

| 目标 | 规模 | 依据 |
|---|---|---|
| `PortfolioORMRepository` 的 10 个 orders 方法与 `db` 裸连接属性 | −300 行（1197→897） | `quant.orders` 已归档不存在 |
| `application/services/order_service.py` | −1175 行 | 文件头自述 DEPRECATED，全部读写下 `quant.orders` |
| `application/services/new_order_service.py` | −102 行 | 仅是对上者的转发壳 |
| 8 个 legacy 测试文件 | 见下 | 100% 测已删模块 |
| `POST /api/signals/execute` | −17 行 | 全仓无调用方，且必 500 |

### 测试侧（**只删 HEAD 上 0 通过、或 100% 测已删模块的**）

先取 HEAD 基线，再决定删/裁，避免误删活路径的覆盖：

| 文件 | HEAD 基线 | 处置 |
|---|---|---|
| `tests/application/services/test_new_order_service.py` | 7 passed | 删（100% 测已删模块） |
| `tests/test_order_trade.py` | 40 failed / 13 passed | 删（模块级 import 已删模块→全文件报错；主体是 order_service） |
| `tests/test_signal_tracking.py` | 3 failed | 删（全篇 legacy 订单链路） |
| `tests/test_order_pnl_tracking.py` | 4 failed | 删 |
| `tests/integration/test_signal_to_order_flow.py` | 2 errors | 删 |
| `tests/e2e_p2_validation.py` | 1 failed | 删 |
| `tests/e2e/test_quant_flow_e2e.py` | 8 errors | 删（16 处 `_update_signal_tracking` 全来自已删模块） |
| `tests/test_live_trading.py` | **39 passed** | **只裁 `TestOrderStateMachine` 9 例**（557→505 行），其余保留 |
| `tests/test_portfolio_repository.py` | — | **只裁 `TestOrders` 类**（339→215 行），保留 `TestTrades` |
| `tests/test_signal_execution_scheduler.py` | — | 改：`mock_create_order` → `mock_paper_engine`；删「限价单价格计算」一例 |

⚠️ **已知覆盖损失**：`test_order_trade.py` 里对 `trade_service`（`record_trade`/`get_trades_by_*`）
的 mock 级覆盖随之消失。这些用例在 HEAD 上本来就有 18 例因 Mock 接口漂移而失败，
但其**尚能通过的 13 例**失去了。建议后续在活路径（simulation_*）上重建。
```
本批不隐瞒这一点：删得掉的是死代码，删不掉的是"本该有的测试"。
```

## 二、顺手修好的真故障：信号执行链**静默失效**

`signal_execution_scheduler._batch_create_orders` 原逻辑：

```python
order_id = create_order(...)      # ← 写 quant.orders，必抛 UndefinedTable
order_ids.append(order_id)
trade_signal = TradeSignal(...)   # ← 上面炸了，这行永远不执行
trade_signals.append(trade_signal)
...
except Exception as e:
    logger.error(f"订单创建失败: ...")
    continue                      # ← 静默吞掉
...
if trade_signals:                 # ← 永远为空
    self.paper_engine.execute_signals(...)   # ← 模拟引擎一单都不执行
```

**后果**：每个交易日，全部通过风控的信号都在 `create_order` 处抛出并被吞掉，
`trade_signals` 恒为空 → **PaperTradingEngine 从未收到任何信号**。
`signal_executions.orders_created` 恒为 0，日志只有"订单创建失败"。
自 2026-08-25 `quant.orders` 归档起，这条链就是死的。

**修复**：删除 legacy 调用，方法回归单一职责（只走模拟引擎，落 `simulation_*` 表）。
返回值改为**实际成交的信号 ID 列表**，调用方取其长度写 `orders_created`
（该列是 `signal_executions` 的真实 DB 列且有路由消费，**名称必须保住**）。

## 三、调用方改法（生产共 4 处，全仓已清零）

| 位置 | 原 | 现 |
|---|---|---|
| `signal_execution_scheduler.py` | import + `create_order(...)` | 删除（见上） |
| `routes/signals_async.py` | `/api/signals/execute` 路由 | 删除端点，留注释说明原委与重建方向 |
| `infrastructure/services/service_factory.py` | `get_order_service()` | 删除（含 cache_clear 行） |
| `adapters/shared/services.py` | `get_order_service()` | 删除（无调用方） |
| `application/services/execution_service.py` | `portfolio_repo.get_order()` legacy 兜底 | 删除（该接口只认券商回报的订单列表） |

**未动**：`domain/legacy/legacy_order_adapter.py` 注入的是**新领域层** `domain.trading.services.order_service.OrderService`（落 `simulation_order`），与 legacy 无关。

## 四、验证

```
定向（5 文件）：1 failed, 77 passed, 1 skipped
  唯一失败 tests/test_portfolio_repository.py::TestTrades::test_record_trade_invalid_symbol
  → 已核在 HEAD 基线失败集合内（pre-existing）
```

广度回归见下节。

## 五、扫描器

`portfolio_repository.py` 15 → **0**：该文件已 100% ORM，
且连 `session.connection().connection`（绕开 session 的裸连接后门）一并关闭。

## 六、遗留

1. `test_order_trade.py` 删除导致的 `trade_service` mock 覆盖损失（见上）。
2. `signals_async.py` 若需重新对外提供"信号→下单"，应基于
   `account_trading_service` / `PaperTradingEngine` 重新设计并明确 `account_name` 语义。
3. `signal_executions.orders_created` 的历史值（归档后恒 0）可作为该故障的时间线证据，
   建议复盘时核对 2026-08-25 至今的取值。
