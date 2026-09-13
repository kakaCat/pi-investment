# REQ-24e15d B4-c1：portfolio_repository 裸 SQL 迁 ORM（trades/holdings 半区）

- 日期：2026-09-14
- 窗口：w-32314d00（投资脑 investor）
- 范围：`adapters/outbound/repositories/portfolio_repository.py` 15 → 6 处
- 前置：B4-b（`87850eb0`）

## 一句话结论

本批把该文件 15 处裸 SQL 中的 **9 处**（get_holdings_stats×3 + 交易/持仓 6 处）落到 ORM；
**剩余 6 处（orders 半区）不是"待迁移"，而是"对着不存在的表写 SQL"** —— 需要决策，故未动。
过程中发现并修复了 2 个**静默缺陷**（不报错、结果错）。

## 一、先摆事实：两个真库核对结果（这一步决定了"能不能机械迁移"）

进入本批前先核对了真库，而不是照着 SQL 文本翻译。结果推翻了原计划的两处前提。

### 事实 1：`quant.orders` 根本不存在

```
information_schema.tables @ quant_investment:
  order/trade 相关表 = ['orders_archived', 'orders_legacy_archived_20260825',
                        'simulation_order', 'simulation_pending_orders',
                        'simulation_trades', ..., 'trades']
  'orders' ∉ 该集合
```

- `orders_archived` / `orders_legacy_archived_20260825` 各 9 行，最新 `created_at` = **2026-08-25 21:02**。
- 实测（2026-09-14）：

```
get_orders() → UndefinedTable: relation "quant.orders" does not exist
```

⇒ 该文件 6 个 orders 站点（get_order / get_orders / create_order /
create_order_with_risk_params / update_order_status / get_order_stats）
**任何 ORM 改写都不会让它工作**：改完只是把 `UndefinedTable` 换成另一个异常。
把它们"迁"了属于伪造进度，故本批**不动**，另开决策（见文末）。

**影响面（已核）**：`signals_async` 路由挂在 `main.py:800`，其
`POST /api/signals/execute` → `new_order_service.create_order_from_signal`
→ `order_service.create_order`（order_service.py:221 **无分支**，直落
`portfolio_repo.create_order`）→ `INSERT INTO quant.orders` → 500。
这是一条**活路由上的真实故障**，不是死代码。

### 事实 2：`quant.trades` 的 action 是**小写**契约，而 ORM 模型写的是大写

```sql
-- 真库 CHECK 约束
trades_action_check | CHECK (action = ANY (ARRAY['buy'::text, 'sell'::text]))
```

- 存量 36 行：`{'buy': 23, 'sell': 13}`，**无一行大写**。
- 而 `models/trade.py` 原先：`CheckConstraint("action IN ('BUY','SELL')") ` +
  `@validates` 调 `normalize_action`（强转大写）。
- 实测大写写入：

```
raw INSERT action='BUY' → IntegrityError: violates check constraint "trades_action_check"
```

⇒ **`Trade` ORM 的写入路径与真库正面冲突（写即炸）**。
这解释了两件事：① 为什么 `record_trade` 只能绕开 ORM 走裸 SQL；
② 为什么 `create_trade()`（早就是 ORM 写法）从没有人用。

⚠️ **关键纪律**：若按原计划把 `record_trade` "机械地"改成 `Trade(**data)`，
就会把**原本能用的代码改成炸的**。裸 SQL 迁 ORM 的前提是先把模型与真库对齐。

## 二、修复 1：Trade 模型 ↔ 真库契约对齐（前置条件）

`models/action_norm.py` 新增（与既有大写契约**方向相反**，刻意如此）：

```python
def normalize_legacy_trade_action(action: str) -> str:
    """quant.trades 专用：归一小写 'buy'/'sell'。"""
```

`models/trade.py` 改 3 处：import、CheckConstraint 文本、`@validates` 调用、列 comment。

**依据**：`action_norm.py` 的模块 docstring 明确列出大写契约只覆盖
`simulation_trades / simulation_order / simulation_pending_orders / signals`
**四张表**——`quant.trades` 不在其中；真库 CHECK 约束是最终裁决。

实测：
```
Trade(action='buy')  → 'buy'     ✅
Trade(action='BUY')  → 'buy'     ✅（大写输入也归一，容错）
Trade(action='hold') → ValueError ✅（非法值仍拒）
```

## 三、修复 2：get_trade_stats 的**静默零**

原 SQL：`COUNT(*) FILTER (WHERE action = 'BUY')` —— **大写**。
真库存小写 ⇒ 36 笔交易被统计成「0 买 0 卖」且**不报错**。

修复前实测：
```
{'total_trades': 36, 'buy_trades': 0, 'sell_trades': 0,
 'total_buy_amount': 0.0, 'total_sell_amount': 0.0, 'total_fee': 166.48}
```

修复后实测（并与独立裸 SQL 口径逐字段核对）：
```
ORM       : {'total_trades': 36, 'buy_trades': 23, 'sell_trades': 13,
             'total_buy_amount': 1197828.7, 'total_sell_amount': 202693.0, 'total_fee': 166.48}
裸SQL独立 : {'t': 36, 'b': 23, 's': 13, 'ba': 1197828.7, 'sa': 202693.0, 'tf': 166.48}
一致性 ✅
```

> 这类缺陷的特征：**不抛异常、字段齐全、只有数值是错的**。
> 光看返回结构完全发现不了——必须拿真库数据对独立口径。

## 四、迁移明细（9 处）

| 方法 | 原 | 现 |
|---|---|---|
| `get_holdings_stats` | 3 次 `cursor.execute` + DictCursor | `session.query(func.count()/sum())` + `group_by` |
| `get_trade` | `SELECT * FROM quant.trades WHERE id=%s` | `query(Trade).filter_by(id=...)` |
| `get_trades_by_symbol` | f-string 拼 WHERE | `query(Trade).filter(...)` |
| `get_trades_by_date` | f-string 拼 WHERE | 同上 |
| `record_trade` | `INSERT ... RETURNING id` | `Trade(**payload)` |
| `get_trade_stats` | `COUNT(*) FILTER (...)` | `func.count().filter(...)` |
| `remove_holding` | `DELETE FROM quant.portfolio_holdings` | `query(...).delete()` |

### 刻意保持的语义（逐条断言过）

1. **日期类型不字符串化**：新增私有 `_trade_to_raw_dict()`，**刻意不用**
   `Trade.to_dict()`——后者会把 `trade_date/created_at` 变 isoformat 字符串，
   而这三个方法的旧契约是 psycopg2 DictCursor 的 `dict(row)`（date/datetime 对象）。
   实测 `isinstance(t['trade_date'], date) == True` ✅
   （对齐历史教训：日期被无条件字符串化后下游 date 运算直接炸）
2. **返回键集合不变**：`get_trade_stats` 保持
   `total_trades/buy_trades/sell_trades/total_buy_amount/total_sell_amount/total_fee`。
3. **invested 不做 COALESCE**：行业/市场分布里 `SUM(total_invested)` 保持可能为
   `None`（原 SQL 未 COALESCE），只有 total_invested/total_cost 做了。
4. **冗余键必须被忽略而非报错**：`record_trade` 用
   `{c.name for c in Trade.__table__.columns} - {'id'}` 白名单过滤
   （原裸 SQL 也只写 11 列）。实测传入 `无关多余键` 未报错 ✅
5. **入参校验与异常语义不变**：`_validate_symbol` / `_validate_date` /
   `action ∈ ('buy','sell')` 前置校验保留；`record_trade`/`remove_holding`
   失败仍抛 `Exception("记录交易失败/删除持仓失败: ...")`。
6. `get_holdings_stats` 原本**无 try/except**（异常向上抛），改写后保持——不新增吞异常。

## 五、真库往返验证（全部 ✅）

```
1. get_trade_stats    与独立裸 SQL 逐字段一致；非零校验通过
2. get_trade          trade_date 是 date 对象；不存在返回 None
3. get_trades_by_*    by_symbol(600519.SH)=3 / by_date=36 / buy=23 / sell=13
                      买卖相加 == 总数；非法 action='BUY' 与非法 symbol 均被拒
4. record_trade       真库往返：insert id=15 → 回读 action='buy'、trade_date=2026-09-14
                      → 冗余键被忽略 → 清理后残留 0（可逆）
5. get_holdings_stats 与裸 SQL 的 sector/market 分布逐条一致（含别名口径修正后）
6. remove_holding     无持仓→False；注入测试持仓→True；二次删除→False（可逆）
```

## 六、回归：0 个新失败

```
定向（7 文件 147 例）：
  本次改动 : 51 failed, 96 passed, 7 skipped
  HEAD     : 51 failed, 96 passed, 7 skipped
  diff(失败集合) → 完全一致  ⇒ 引入 0 个新失败
```

既有失败的根因（与本批无关，已在 HEAD 复现）：
- `test_order_trade.py` 大量 `AttributeError: Mock object has no attribute 'get_trade_stats'`
  —— MagicMock spec 与接口漂移；
- `test_multi_account_domain.py` `UndefinedColumn: column "decision_price" of relation
  "simulation_order" does not exist` —— **测试库 quant_test 的 schema 落后于 ORM 模型**
  （`SimulationOrder` 已含 decision_price/decision_at/price_source/fill_price/slippage_bps，
  测试库没有）。这是环境漂移，建议单独立项修 quant_test schema。

## 七、扫描器指标

| 指标 | 本批前 | 本批后 |
|---|---|---|
| `portfolio_repository.py` 站点 | 15 | **6**（全部为 orders 半区，已定性） |
| `cursor_execute`（本轮范围） | 60 | **51** |
| P0（fstring_value_interp / raw_connect） | 0 | 0 |

## 八、遗留决策（需人工/架构裁定，非本窗口可自决）

**`portfolio_repository.py` 的 6 个 orders 方法怎么办？** 三个选项：

- **A. 删除**（推荐）：`quant.orders` 已归档、现役订单在 `simulation_order`。
  连带清理 `application/services/order_service.py`（文件头已标 DEPRECATED）、
  `new_order_service.py` 的委托、以及 `signals_async.py` 的 `/api/signals/execute`
  或改为走 `account_trading_service`。
- **B. 改指向 `simulation_order`**：语义重构（shares/price_limit/numeric 类型、
  account_name 维度），工作量 ≥ 一次单独需求，且要同步改调用方。
- **C. 只加显式护栏**：保留方法但在入口抛 `NotImplementedError` 带说明，
  避免"已归档表"继续以 500 形式暴露。

在裁定前，这 6 处**保持原样**——把它们改成 ORM 只会掩盖问题（见"事实 1"）。
