# 策略状态语义：结构有效 ≠ 业绩有效

**立此文档的原因（2026-09-13 真实案例，w-a9ec14d7）**：只有一个 `validation_status` 字段，被同时当成两种含义使用，
于是"valid"被一路读成"这策略好用"——而实测 14 条 `active + valid` 策略在**相对同池等权基准**的口径下，
OOS 年化中位约 **−1%**（区间 −3.32% ~ +2.65%），同期基准 **+23.3%**，**没有一条跑赢**。

## 两根轴（必须分开读写）

| 字段 | 含义 | 取值 | 谁写 |
|---|---|---|---|
| `structure_status` | 代码/参数**能不能跑通** | `valid` / `invalid` / `pending` / `unknown` | 代码校验、批量回测验证 |
| `performance_status` | 跑通之后**有没有超额** | `passing` / `underperform` / `failing` / `unmeasured` | 回测证据 + 基准比较 |

- 判定规则**单一事实源**：`quantsys-v2/application/services/strategy_status.py`（`classify_structure` / `classify_performance`）。
- 业绩判定一律**相对基准**，不用绝对收益阈值：`ar<=0→failing`；`0<ar<基准→underperform`；`ar>=基准→passing`；无证据→`unmeasured`。
  依据：绝对阈值在本市场无意义——同期同池等权基准 CAGR 就有 **+23.3%**（2024-07~2026-09，800 只、2024H1 定义的最活跃池），
  任何"年化 >8% 就算好"的门槛都会被 beta 跟随轻松通过。
- `unmeasured` 是**诚实的默认值**：没有证据就写"没测过"，不允许把无证据冒充达标。

## 遗留字段 `validation_status` 的地位

`validation_status` **保留**（大量历史读路径依赖），但它的语义被钉死为**结构轴**：等价于 `structure_status`，
写入时会双写 `structure_status`。**任何把 `validation_status=valid` 当作"业绩好"的读法都是错的。**

## API 暴露（FastAPI，响应经 camelCase 转换）

`GET /api/strategies/list`、`GET /api/strategies/detail/{id}` 的每个 item 含：

```
structureStatus      "valid" | "invalid" | "pending" | "unknown"
performanceStatus    "passing" | "underperform" | "failing" | "unmeasured"
performanceEvidence  {annual_return, sharpe, max_drawdown, benchmark_cagr, benchmark_note, source, window, rule}
performanceCheckedAt 判定时间
statusSemantics      自解释文案：status 仅由结构轴派生，不代表业绩
```

⚠️ `status`（`stopped`/`error`/`running`）由结构轴派生：`valid→stopped`、`invalid→error`。
**`status=error` 是"结构无效"，不是"运行出错"，更不是"业绩差"。** 这是本次拆分的直接动因——
`enrich_strategy_response` 把结构判定映射成了运行态外观。

## 消费方纪律（agent 侧）

- R-011 的"信号源健康核验"应改为读两根轴：**`structure_status != valid` 或 `performance_status` 为 `failing`/`underperform` → 输出不可信**。
  （原文只写 `status=error / validationStatus=invalid`，会漏掉"结构 valid 但业绩 failing"这一大类，实测它就是多数。）
- `unmeasured` 不等于可用：无证据的策略只能进观察，不能当信号源。

## 写路径

- `StrategyORMRepository.update_validation_status()` → 同时写 `structure_status`（双写，单一入口）。
- `StrategyORMRepository.update_performance_status()` → 写 `performance_status` + `performance_evidence` + `performance_checked_at`。
- `StrategyValidationService.validate_from_recent_backtests()` → 用同一份回测证据**同时**写两根轴（业绩判定失败不影响验证主流程）。
- 历史数据回填：`quantsys-v2/scripts/backfill_strategy_status.py`（支持 `--lab` 接入 T+1/含成本/OOS 口径的体检结果）。