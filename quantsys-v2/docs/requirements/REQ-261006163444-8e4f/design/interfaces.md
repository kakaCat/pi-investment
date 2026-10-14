# REQ-261006163444-8e4f · 设计：接口与契约

> 本文件是拆分阶段的"契约底本"：签名、字段、错误语义在此定死；定不死的进不了拆分。

## 1. 新模块 `application/services/kline_domain.py`（serves: FR-1, FR-3）

```python
TRADABLE_MAX_GAP = 0      # gap == 0 ⇒ 可交易域
STOCK_MIN_GAP = 5         # gap >= 5 ⇒ 存量；1..4 ⇒ 观察中
UNKNOWN_GAP = 9999        # mx 不在交易日集合内（脏数据）时的哨兵

@dataclass(frozen=True)
class DomainSnapshot:
    last_trade_date: Optional[str]        # 'YYYY-MM-DD'；无数据时 None
    prev_trade_date: Optional[str]        # 倒数第二个交易日；不足两个时 None
    gap_days: Mapping[str, int]           # symbol -> 连续无数据交易日数（0 = 末日有 K 线）
    tradable: frozenset[str]              # gap == 0
    observing: frozenset[str]             # 1 <= gap <= 4
    stock: frozenset[str]                 # gap >= 5（含 UNKNOWN_GAP）
    dropped_new: frozenset[str]           # gap == 1（上期在域、本期不在）
    dropped_known: bool                   # prev_trade_date 可得 ⇒ True；否则掉出不可判
    degraded: bool                        # 快照不可用（无交易日/查询失败）
    degrade_reason: Optional[str]

def classify_domain(
    trade_dates_desc: Sequence[str],                 # 交易日倒序，[0] = D_last
    symbol_last_dates: Sequence[tuple[str, str]],    # (symbol, 该标的最后有 K 线的交易日)
) -> DomainSnapshot:
    """纯函数：无 DB、无 I/O、无副作用 ⇒ 可脱离数据库单测。"""

def build_domain_snapshot(kline_repo) -> DomainSnapshot:
    """编排：调仓储两个只读方法 → classify_domain；查询异常 ⇒ degraded=True（不抛）。"""
```

**契约细则**

- `gap` = 交易日倒序名次减一：`gap = rank(mx) - 1`（`rank` 按交易日倒序，`D_last` 名次为 1）
  ⇒ `mx == D_last` 时 `gap = 0`，`mx == prev_trade_date` 时 `gap = 1`。
  （订正：本节初稿误写为 `rank(D_last) - rank(mx)`，与实现不符；2026-10-06 实施 t1 时订正为上式。）
- 三个集合**两两不相交**且 `tradable | observing | stock == set(gap_days)`（用例锁住，test-cases.md §1）。
- `dropped_new == {s for s, g in gap_days.items() if g == 1}`，与 `prev_trade_date` 的存在无关；
  但 `dropped_known=False` 时**调用方不得**把 `dropped_new` 当结论（正文写"无上期交易日，掉出不可判"）。
- 不抛异常：任何查询/解析失败都收敛成 `degraded=True` + `degrade_reason=<摘要>`，由调用方响亮处理（§7）。

## 2. 仓储契约（serves: FR-1, FR-2）

### 2.1 `KlineORMRepository`（`adapters/outbound/repositories/kline_repository.py`，新增两个只读方法）（serves: FR-1）

```python
def list_recent_trade_dates(self, limit: int = 2) -> list[str]:
    """全市场交易日倒序前 limit 个（'YYYY-MM-DD'）。SQL 见 data-model.md §2。"""

def list_symbol_last_trade_date(self) -> list[tuple[str, str]]:
    """(symbol, 该标的最新的有 K 线交易日) 全量；不加时间过滤。"""
```

- **同类数据访问收口**：`daily_klines` 只由本仓储读；不在 job 或 service 里写裸 SQL
  （`_check_quality_alerts` 的裸 SQL 历史包袱已在 `w-32314d00` 清过一次，不再回退）。
- **同步轨**：本路径全在调度线程内（同步），用 sync 仓储；不新增 async 对应实现。

### 2.2 `KlineQualityRepository.count_by_grade_on`（语义修正，签名向后兼容）（serves: FR-2）

```python
def count_by_grade_on(
    self, grade: str, day: Optional[_date] = None,
    symbols: Optional[Collection[str]] = None,
) -> int:
    """某日某评级的 **distinct 标的** 数（语义修正：原为行数）。
    symbols 非空时限定在该集合内（用于域内计数与交叉核对）。"""
```

- **行为变更（有意）**：不传 `symbols` 时返回值从"当日行数"变为"当日 distinct 标的数"
  ⇒ 今日口径 **806 → 404**（E3）。既有两处调用（`data_quality_check_job.py:407/411`）都只传 grade，
  语义随之改变——这是 FR-2 ② 的目的，**不是**回归。
- **保留"当日"语义**：仍按 `func.date(created_at) == target` 过滤，不引入 run 概念；
  `_safe_rollback` 的失败重试语义不变。
- **退出主路径**：本次告警统计改读 `per_symbol`（§3），`count_by_grade_on` 仅供人复核与后续复用；
  若 `per_symbol` 不可用则**不**回退到它（避免引入第二个真相源，见 §7 降级分支）。

## 3. `DataQualityService.check_data_quality` 返回契约（serves: FR-2）

签名不变：

```python
def check_data_quality(self, symbols=None, start_date=None, end_date=None,
                       include_report=False, deadline=None) -> Dict
```

返回值**新增一个键**（只增不改，其余键语义不变）：

```python
{
  "summary": {...},              # 既有：全库口径（保留，不删；告警不再用它判阈值）
  "stocks_with_issues": [...],   # 既有：展示用，仍截断 [:50]
  "per_symbol": {                # 新增：全量事实（形状见 data-model.md §6）
     "600519": {"coverage_rate": 100.0, "missing_days_count": 0,
                "quality_score": 93.33, "overall_score": 97.78, "grade": "A",
                "has_duplicates": False, "has_anomalies": True, "anomaly_unknown": False},
     ...
  },
  "report_url": "..."            # 既有（include_report 时）
}
```

- **全量**：`per_symbol` 覆盖本次传入的全部 `symbols`（`check_truncated=True` 时为已扫描子集），
  不受 `[:50]` 截断影响 ⇒ 解除"统计读展示明细"的耦合（纪律 B）。
- **`grade` 单点计算**：`overall_score → _calculate_grade` 在循环内算一次，
  `per_symbol` 与 `_persist_quality_audit` **共用同一个值**（禁止两处各算一遍）。
- **兼容**：其他调用方（`adapters/inbound/fastapi_app/routes/data_quality_async.py:162`、
  `tests/test_data_validator_anomaly_detection.py:212`）只读既有键，新增键对其透明。

## 4. 作业层契约（serves: FR-1, FR-2, FR-3, FR-4）

### 4.1 `daily_data_quality_check(**params)` 流程（`infrastructure/jobs/data_quality_check_job.py`）（serves: FR-1, FR-3, FR-4）

```
_normalize_params(params)                      # 新增三个键的钳制与 notes（§6）
  ↓
domain = build_domain_snapshot(service.kline_repo)      # 新增：检查前建快照
  ↓
quality_result = service.check_data_quality(...)        # :184 不变
  ↓
backfill targets = 全量 per_symbol ∩ domain.tradable     # 改：不再用 stocks_with_issues[:50]
  ↓
result = {...}                                          # :295 结果构造
  ↓
_check_quality_alerts(result, domain, per_symbol, thresholds)   # 新签名
```

- 快照在**检查前**建（口径与数据同源：`daily_klines` 不因本次检查而变化）。
- 回填目标排序仍为"缺失天数降序"，但候选集已是**域内**（死标的天然出局）⇒ 排序不再指向必败目标。

### 4.2 告警检查函数（签名变更）（serves: FR-2, FR-3, FR-4）

```python
def _check_quality_alerts(
    result: Dict[str, Any],
    domain: DomainSnapshot,
    per_symbol: Mapping[str, Mapping[str, Any]],
    thresholds: Mapping[str, float],     # {'d_grade','score','coverage_info','backfill_fail_rate','backfill_min_sample'}
) -> Optional[Dict[str, Any]]:
    """在 result 上补写 domain / domain_dropped / alert_thresholds / alert_dispatch；
    返回外发回执（与既有 alert_dispatch 同义）。不抛：内部失败转 error 告警（§7）。"""
```

### 4.3 统计聚合契约（serves: FR-2, FR-4）

```python
@dataclass(frozen=True)
class DomainStats:
    last_trade_date: Optional[str]
    tradable: int; observing: int; stock: int          # 快照计数
    stats_symbols: int                                  # 实际参与均值的只数 = |tradable ∩ per_symbol|
    partial: bool                                       # stats_symbols < tradable（检查被预算截断）
    d_grade: int                                        # 域内 grade == 'D' 的只数
    mean_score: float                                   # 域内 quality_score 均值（stats_symbols == 0 时为 nan）
    mean_coverage: float
    dropped_count: int; dropped_symbols: tuple[str, ...]; dropped_truncated: bool
    backfill_total: int; backfill_failed: int
```

- `mean_score` 用 **`quality_score`（= accuracy_score）**，与既有 `summary['data_quality_score']` 同口径，
  保证"绿/红"的历史可比性（不换指标含义，只换分母）。
- `stats_symbols == 0` ⇒ 不判域内阈值，转 error 告警 `qa_scope_unavailable`（§7）。

## 5. 告警正文契约（serves: FR-2, FR-3, FR-4）

```
📊 数据质量告警（N 项）
时间: <ts>
口径: 可交易域（最后交易日 2026-09-30）｜统计 5280/5280 只

检查域:
  可交易 5280 ｜ 观察中 3 ｜ 存量 403

本期掉出可交易域: 2 只
  002813 路畅科技, 603183 建研院            ← 上限 20 只；超出写 "…等 N 只（只显示前 20）"

域内指标:
  评分 90.84（阈值 88.0）
  平均覆盖率 98.54%（信息项，阈值 97.0）
  D级 3 只（阈值 20）

问题清单:
  ⚠️ 本期掉出可交易域: 2 只（warning）
  ...（域内阈值越线项，按既有 level 规则）

回填: 目标 12 只（域内）｜失败 3 只 → 失败率 25.0%
      (样本 n < 10 时写 "样本 n=7 < 10，不判失败率")
```

- **标题项数** = `len(alerts)`；健康日典型为 1 项（掉出域 warning）。
- **信息项不产生 alert**：覆盖率均值只进正文，不进 `alerts`（不改变 `alert_count`）。
- **`urgency` 规则不变**：有 `error`/`critical` 用 `high`，否则 `normal`。
- 掉出域用 **warning**（D-4 明确"不直接报 error"）；存量只报数不点名（避免每日重复噪音）。

## 6. 参数契约（`_normalize_params`）（serves: FR-4）

| 参数键 | 缺省 | 类型/范围 | 出现位置 |
|---|---|---|---|
| `d_grade_threshold` | 20 | int ≥ 0 | `effective_params` + `param_notes` |
| `quality_threshold` | **88.0**（原 90.0） | float 0..100 | 同上 |
| `coverage_info_threshold` | 97.0 | float 0..100 | 同上 |
| `backfill_fail_rate_threshold` | 50.0 | float 0..100 | 同上 |
| `backfill_min_sample` | 10 | int ≥ 1 | 同上 |

- 非法值一律回落缺省并写 `param_notes`（沿用既有防呆风格，禁止静默）；
- 五个键全部进 `result['alert_thresholds']`，让"配置了没生效"可核验。

## 7. 错误语义与日志（serves: FR-1, FR-3）

| 情形 | 处置（一律响亮，不静默降级） |
|---|---|
| 快照 `degraded=True`（查不到交易日/查询异常） | 不发域内阈值告警；发 **error** 项 `qa_scope_unavailable`（附 `degrade_reason`）；`result['alert_scope']="degraded"`；正文写"⚠️ 分域不可用，本次未做域内判定" |
| `per_symbol` 缺失或为空（旧替身/上游契约漂移） | 同上走 `qa_scope_unavailable`，并在日志 error 点名"`per_symbol` 缺失"；**不回退**到 `count_by_grade_on` |
| 无 `prev_trade_date` | `domain_dropped.reason="no_prev_trade_date"`，正文写"无上期交易日，掉出不可判"；**不报** warning |
| `partial=True`（检查被预算截断） | 正文写"统计 4120/5280 只（检查触达预算，已截断）"；仍判阈值，但 `alert_thresholds` 与正文都标 `partial` |
| `mx` 不在交易日集合（脏数据） | `gap=UNKNOWN_GAP` → 落存量；日志 warning 点名 symbol（上限 20 条，超出报计数） |
| 域内无可统计标的（`stats_symbols==0`） | error 项 `qa_scope_unavailable` |
| 回填分母 < `backfill_min_sample` | 不判失败率；正文写明样本与门槛 |
| 告警外发失败 | 既有语义不变（`delivered=False` 落 `alert_dispatch`，只记日志不影响 run 结果） |

## 8. 静态与兼容红线（serves: FR-2, FR-6）

1. **裸 SQL 只许出现在仓储层**；`kline_domain.py` 是纯函数（无 `import` DB）。
   规范依据：`reqboard_kb(kind='standard')` → `kb-conventions-c01`「层边界只许向内」
   （`conventions.md#c-01`）——分域逻辑放在应用层（内），数据访问留在适配器层（外），
   依赖方向只有"应用层引用仓储"，不得反过来。
2. **同步轨**：新增仓储方法只加在 sync 仓储，不新建 async 对应实现（口径见 CLAUDE.md「仓储双轨口径」）。
3. **不得**在 job 内对 `daily_klines` 直接 `text()` 查询。
4. **`per_symbol` 不得进入 `result`/日志全文**（只进聚合结果），否则 jsonb 膨胀（data-model.md §4）。
5. **同一事实一个真相源**：域内 D 级数来自 `per_symbol`；`count_by_grade_on` 只做人复核口径，
   两条路径的差异由 test-cases.md §3.2 的交叉核对命令显式暴露（今日应相等：404）。
6. 返回键集向后兼容：所有既有键保留，新增键只增不改（`check_data_quality` / `result` /
   `count_by_grade_on` 三处都适用）。
