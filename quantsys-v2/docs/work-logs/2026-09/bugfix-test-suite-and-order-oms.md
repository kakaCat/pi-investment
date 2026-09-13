# bug 修复批次 —— 测试套件可跑通专项（2026-09-14，w-32314d00）

**背景**：上一批次（B1）交付时留下 3 条"与本批无关但确实红着"的记录。用户指示
「先修 bug，再做 B2」。本文件记录这批修复的根因、证据与验证。

**结论先行**：6 类问题全部修完，其中 **3 个是生产代码的真缺陷**（不是测试问题）：
① 空 K 线喂 TA-Lib 会破坏堆 → 整个进程段错误；
② 订单状态机缺 (PENDING→FILLED) → **一次全量成交永远失败**；
③ 订单服务调用的持仓/资金方法根本不存在 → 成交后持仓与资金永不更新。

---

## Bug1 `cninfo_disclosure`：测试与实现脱节 + **orgId 失败被永久静默缓存**（真缺陷）

### 现象
`tests/.../test_cninfo_disclosure.py` 2 failed（`len(None)` / `24 != 20`）。

### 根因（两层）
1. **测试脱节**：测试写在 `d2ffb396`，而 provider 在 `b640cf0c` 引入了 orgId 解析
   —— 此后**每只标的是两次 HTTP**（topSearch 解析 orgId + hisAnnouncement 查询），
   测试仍只喂一个响应。更糟的是：它把 orgId 写进**模块级**失败缓存，
   后续用例于是静默走 searchkey 回退路径 —— **测试"通过"，但测的根本不是主路径**。
   （这正是这个 provider 自己要防的静默少收模式，只不过发生在测试层。）
2. **生产缺陷**：`_resolve_org_id` 把失败也写成空串长期缓存：
   ```python
   _ORG_CACHE[symbol] = ''      # 解析失败也缓存
   ...
   if symbol in _ORG_CACHE: return _ORG_CACHE[symbol] or None   # 直接返回，连日志都不打
   ```
   于是一次瞬时网络抖动 → 该标的**整个进程生命周期**都走 searchkey 回退（已知会少收），
   且**再也不会告警**：降级从"一次告警"变成"永久静默"。

### 修法
- 缓存拆两张表：成功长期缓存；**失败只做 10 分钟 TTL 缓存**，且每次命中都再告警一次
  （`_ORG_FAIL_CACHE` + `_ORG_FAIL_TTL_SECONDS`）。
- 测试：按真实调用序列喂响应（topSearch → 查询）；加 autouse 夹具清缓存；
  补 3 条用例分别锁 **主路径必须 stock=<code>,<orgId>**、**回退必须可见**、**失败缓存有 TTL 且命中仍告警**。

### 验证
`15 passed`（原 13 项 2 失败）。

---

## Bug2 `handle_factor_compute`：测试 patch 了一个**不存在**的函数

### 现象
`test_scheduled_jobs_account_value.py::test_compute_and_persist_via_factor_stage`:
`AttributeError: service_factory has no attribute 'get_data_service'`。

### 根因
实现已在 2026-09-03 / 2026-09-10 两次修复中改为**直接走仓储**
（`KlineORMRepository.get_daily_klines` / `FactorORMRepository.save_factors`），
而测试仍 patch 早已不存在的 `service_factory.get_data_service`。

### 修法
patch 点落回真实调用链（仓储方法 + `_filter_factor_universe` + 资金流 helper 的**源模块**，
注意后者是在函数体内 import 的）；替身 FactorStage 补齐 `DEFAULT_TECHNICAL_FACTORS`
（缺它会被逐标的 except 吞成 failed，与真实缺陷无法区分）。

### 验证
`3 passed`。

---

## Bug3 **空 K 线喂 TA-Lib → 堆内存破坏 → 进程段错误**（真缺陷·最严重）

### 现象
`tests/services/test_strategy_factor_injector.py` 第 2 个用例直接把 **pytest 进程打死**
（`Trace/BPT trap: 5`；设 `POLARS_MAX_THREADS=4` 后变 `Abort trap: 6` 并打出 traceback），
faulthandler 指到 `strategy_factor_injector.py:343/370` 的 `df[method] = np.nan`。
**整个 5824 条用例的全量测试因此跑不完**（多种环境变量下分别表现为 SIGTRAP/SIGABRT/SIGSEGV）。

### 定位过程（关键是受控 A/B，而不是猜）
1. 逐个调用 TA-Lib 因子方法（`apo`/`bop`/`willr`/`trix`…）→ 都只是 `IndexError`，**不崩**；
2. 纯 pandas 循环（空 DataFrame 逐列赋值 40 次）→ 正常；
3. **受控对比**：同一个「空 DataFrame 逐列赋值」循环
   —— **不调 TA-Lib** 跑 4 次：**4/4 EXIT=0**；
   —— **调 TA-Lib** 跑 2 次：**2/2 Trace/BPT trap**，且崩溃点在不同因子间漂移
      （一次在 `willr`、一次在 `trix`）。
   ⇒ 结论：**TA-Lib 在 0 长度输入下破坏堆内存**；崩溃现场在几层之外的 pandas 列赋值处，
     根因与症状相距极远，极易被误判成"pandas 的 bug"。

### 修法（两层）
1. `StrategyFactorInjector.inject_all_factors`：空 K 线**提前返回**（这也是该用例的契约；
   原实现还会执行 `klines[0].keys()` → 空输入必 IndexError）。
2. `domain/factors/library/base.py`：新增 `_require_non_empty`，并在 5 个
   `_extract_close/open/high/low/volume` 入口拒绝空输入 —— **绝不让 0 长度数组到达原生库**。
   抛 `InsufficientDataError` 而非返回空数组，是为了让问题在上一层以可捕获的异常暴露，
   并被 per-method try/except 降级成 NaN 因子，而不是在原生层以内存破坏形式爆发。

### 验证
该文件 `7 passed`；`pytest tests/services/test_strategy_factor_injector.py` 不再杀进程。

---

## Bug4 订单状态机：**一次全量成交永远失败** + 重复定义 + 协作者 API 全错位（真缺陷）

### 4.1 `VALID_TRANSITIONS` 缺 `(PENDING, FILLED)`
挂单后**一次全部成交**（市价单 / 限价单被一次吃满）是最常见路径，而该表只允许
`PENDING→PARTIAL→FILLED`，于是 `fill_order` 对这种单子恒抛
`ValueError("非法状态转换: pending -> filled")`。**整单成交 100% 失败**。

### 4.2 `OrderService` 有两个 `_validate_status_transition`（行 46 与 173）
Python 取最后一个 → **第一个（带幂等处理）成为死代码**，而存活的那个
**丢掉了"相同状态视为幂等 no-op"**：重复上报同一状态会错误地抛异常。
（测试 `test_idempotent_transition_same_status` 正是锁这条契约。）

### 4.3 调用的协作者方法**根本不存在**
```python
self.position_service.add_shares(...)    # PositionService 只有 update_on_buy / update_on_sell
self.position_service.reduce_shares(...) # 同上
self.account_service.deduct_funds(...)   # AccountService 只有 execute_deduct_cash
self.account_service.add_funds(...)      # 只有 execute_add_cash
```
任何**真实**（非 Mock）调用都会 `AttributeError` —— 成交后持仓与资金永不更新。

### 修法
- 状态表补 `(PENDING, FILLED)` 并留证伪说明；
- 删掉重复定义，保留带幂等语义的那一份；
- 调用改为真实 API，并把已算好的 `commission/stamp_duty/transfer_fee` **透传**给持仓服务
  （原写法只传成交价 → 持仓成本不含费用，买入成本被系统性低估）。

### 4.4 顺带修正一条**断言本身与状态机矛盾**的测试
`test_cancel_order_not_pending` 断言文案"只能取消 pending 状态的订单"，但
`VALID_TRANSITIONS` 明确允许 `PARTIAL → CANCELLED`（部分成交当然可以撤）。
真正的规则是"终态不可再撤"，故改为断言状态机拒绝并报出 filled 这个终态。

### 验证
`tests/domain/trading`：**50 passed**（原 8 failed）。

> ⚠️ 范围说明：`domain/trading/services/order_service.py` 目前**无生产调用方**
> （`DomainServiceFactory` 全仓只在自身定义处出现），属未接线的 DDD 迁移半成品。
> 本次修的是"这段代码一旦被接线就会立刻坏"的真缺陷，**没有**去动它的接线决策。

---

## Bug5 `MLflowManager` 默认后端在 mlflow 3.x 上**构造即抛异常**

mlflow 3.x 起 filesystem tracking backend 进入 maintenance mode，**默认直接抛
MlflowException**（官方逃生口是 `MLFLOW_ALLOW_FILE_STORE=true`）。而本仓默认就是
`file:./mlruns`，于是 5 个用例全 ERROR（真实使用同样起不来）。

修法：`_ensure_file_store_allowed()` —— 只在**确实用 file store**时显式 opt-out 并写警告日志；
用户若已显式设过该变量（哪怕 =false）则完全尊重，不覆盖。
顺带支持 `MLFLOW_TRACKING_URI` 覆盖默认值，并把测试跑出来的 `mlruns/` 加进 `.gitignore`。

验证：`tests/test_ml` **14 passed**（原 9 passed / 5 errors）。

---

## Bug6 `test_brokers.py`：注册表未注册 + 枚举大小写漂移

- 5 个 Registry 用例：`setup_method` 只 `reset()` 不注册，而该注册表**按设计是空表**
  （docstring 明写"须由基础设施层 setup_brokers() 注册"）→ 补上注册；
- 2 个枚举用例：`49a3caf2 "Batch-1: 统一 action 大小写契约为 'BUY'/'SELL'"` 已把契约
  **刻意改成大写**，测试未同步 → 断言改为锁定现行大写契约（改回去会让下单方向静默失配）。

验证：**17 passed, 3 skipped**（原 7 failed）。

---

## 遗留（已定位、非本批修）

- **全量 `pytest tests/` 仍会在 `tests/test_ml/test_transformer_predictor.py` 处段错误**，
  但该文件**单独跑 4 passed、`pytest tests/test_ml` 14 passed**，只有和其他前置用例
  跑在同一进程里才崩（heap/原生库状态相关）——属**环境级原生库冲突**（torch/numba/talib 同进程），
  不是产品缺陷。可跑的分片命令：
  ```
  pytest tests/ --ignore=tests/e2e --ignore=tests/test_ml
  pytest tests/test_ml
  ```
