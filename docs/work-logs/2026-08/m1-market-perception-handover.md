# M1 市场感知实施交接单（领工指南）

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-21 |
| 编制 | agent-dh k3（审计+文档角色，不实施） |
| 实施方 | 待领工（其他 agent） |
| 上游设计 | [RFC 007 M1 市场感知实施方案](../../rfcs/007-market-perception-m1-implementation.md) |
| 分支 | `feat/m1-market-perception`（当前仅含 RFC 007 文档提交 71680a73） |

---

## 0. 现状盘点（已完成的不要重做）

- ✅ 三张表**已在生产 PG 建好**（`quant.market_regime` / `quant.market_sentiment_daily` / `quant.market_theme`，迁移 SQL 内容见本文 §5，可直接复用为 `quantsys-v2/migrations/create_market_perception_tables.sql`）
- ✅ 设计评审完成（RFC 007）
- ⚠️ 曾在 worktree 写过一版完整实现（服务+路由+main.py 注册，约 500 行），**worktree 被外部删除导致代码丢失**，本文 §4 保留了关键实现要点与模式，实施者可按此重写
- ⚠️ worktree `.claude/worktrees/m1-market-perception` 已不存在，开工先重建：`git worktree add .claude/worktrees/m1-market-perception feat/m1-market-perception`

## 1. 🔴 P0 前置阻断：settings.py 坏合并（必须先修，否则后端无法重启）

### 根因链（已审计确认）

| 证据 | 结论 |
|---|---|
| merge `c076bd24`（P1-2 架构迁移） | 拿了新版 `infrastructure/config/__init__.py`（import Config/get_config/...），却配了旧版 settings.py（无 Config） |
| `git show 3c4c3554:.../settings.py` | **完整统一版存在**（208 行，含 class Config、get_config、RedisSettings、ProxySettings、ThreadSettings、AppSettings.memory_recall_cosine_floor 等） |
| `git show HEAD:.../settings.py` | 210 行旧版（AppSettings/get_settings 风格，无 Config） |
| 实测（2026-08-20） | 新鲜检出 `import infrastructure.config` → ImportError: cannot import name 'Config'；main 树则触发 pydantic extra_forbidden（memory_recall_cosine_floor） |
| 运行中的后端（PID 47699, 20:01 启动） | **靠 stale __pycache__ 侥幸存活**——任何重启都可能起不来，⚠️ 修复前禁止重启后端 |

### 修复规格（实施者照做）

1. 恢复：`git show 3c4c3554:quantsys-v2/infrastructure/config/settings.py > quantsys-v2/infrastructure/config/settings.py`
2. **追加 HEAD 兼容层**（HEAD 风格调用点不能断）：
   - `DatabaseSettings` 增加连接池字段：`pool_size`(20) / `max_overflow`(20) / `pool_recycle`(3600) / `pool_pre_ping`(true)，env 别名兼容 `DB_POOL_SIZE` 等（用 `AliasChoices`）——消费点：`fastapi_app/main.py:66`
   - `LoggingSettings` 增加别名属性：`log_level` → `level`、`log_format` → `format`——消费点：`fastapi_app/main.py:41-42`
   - 新增 `SchedulerSettings`（字段：tick_interval=60、misfire_grace_time=300、agent_os_enabled、agent_os_url）
   - 新增 `ThreadPoolSettings` 外观（default_workers=10 / io_workers=20 / compute_workers=4，env: DEFAULT_POOL_WORKERS 等）——消费点：`infrastructure/threading/thread_pool.py:164`
   - 新增 `get_settings()` / `reload_settings()`：返回外观对象，暴露 `.logging` / `.database` / `.thread_pool` / `.scheduler` / `.environment` / `.is_production` / `.is_test`；文件末尾保留 `settings = get_settings()` 模块级单例（旧代码有引用）
3. 验收（全部要在**干净环境**跑，先删 `__pycache__`）：
   ```bash
   find quantsys-v2/infrastructure/config -name __pycache__ -exec rm -rf {} +
   cd quantsys-v2 && ./venv/bin/python -c "
   from infrastructure.config import get_config
   from infrastructure.config.settings import get_settings
   c = get_config(); s = get_settings()
   assert c.database.url.startswith('postgresql')
   assert s.database.pool_size == 20 and s.logging.log_level
   from infrastructure.persistence.orm import get_session; get_session()
   print('config fix OK')"
   ```
4. 修完后**重启后端并验证**（这是验证修复的唯一方式）：停止必须走 `stop.sh` 精确停止（多实例铁律，禁止 pkill 模糊匹配）。若启动失败，回滚 settings.py 并上报。

## 2. M1 服务实现要点（重写指南）

### 文件清单

| 文件 | 内容 |
|---|---|
| `quantsys-v2/migrations/create_market_perception_tables.sql` | §5 的 DDL（已应用，入库即可） |
| `quantsys-v2/application/services/market_perception_service.py` | 核心服务（见 §3 结构） |
| `quantsys-v2/adapters/inbound/fastapi_app/routes/market_perception_async.py` | 7 个端点（见 §4） |
| `quantsys-v2/adapters/inbound/fastapi_app/main.py` | 注册路由：插在 "market_data (market/hk 迁移)" 块之后（约 471 行），用同样的 try/except ImportError 可选路由模式 |

### 已验证的集成模式（照抄即可，都是实测趟出来的）

1. **DB 访问**：`from infrastructure.persistence.orm import get_session` + `session.execute(text(...))`（参照 `data_quality_async.py` 的 `_factor_freshness_check`）
2. **情绪计算复用**：`MarketSentimentService(ds).analyze_market_sentiment()`，返回 snake_case：`indicators.advance_decline{up_count,down_count,flat_count,ratio,data_date}`、`volume{volume_ratio,recent_avg_volume}`、`volatility{volatility}`、`new_high_low{new_high_count,new_low_count}`、顶层 `fear_greed_index`
3. **⚠️ ds 不要用完整 DataService**：`ServiceFactory.get_data_service()` 会拉起 tushare→infrastructure.config 重链。MarketSentimentService 全程只用 `ds.kline.*`，用轻量 shim：
   ```python
   class _KlineOnlyDS:
       def __init__(self):
           from adapters.outbound.repositories import KlineORMRepository
           self.kline = KlineORMRepository()
   ```
4. **指数趋势**：`get_data_provider_manager().get_index_daily('sh000300')`（daily_klines 里**没有**指数——'000001' 是平安银行冲突）。records 键兼容中文（收盘/日期）与英文（close/date），按日期升序排序后算 MA20/MA60/5日涨跌
5. **涨停池**：`get_data_provider_manager().get_zt_pool(date)` → `result['data'].data['records']`，中文字段：`代码/名称/涨跌幅/最新价/换手率/封板资金/所属行业`（参照 `manipulation_detector.py:145-175` 的既有用法）
6. **regime 判定规则**：按 RFC 007 §3 表（panic→euphoria→trend_up→trend_down→range 优先级），reason 字段必须含全部原始指标值
7. **主线聚类**：按"所属行业"分组，≥3 只成团，按（涨停数, 封板资金合计）排序取 Top3；落库前 `DELETE ... WHERE trade_date=:d AND catalyst IS NULL` 保证幂等重跑且不覆盖 LLM 回写

## 3. 服务结构（market_perception_service.py）

```
MarketPerceptionService(ds=None)   # ds=None 时用 _KlineOnlyDS
├─ run_daily_snapshot(trade_date=None)     # 编排：情绪→regime→主线，逐步容错
├─ _snapshot_sentiment(trade_date)         # M1-3：调 MarketSentimentService 落库，
│                                          #   coverage<4000 → partial=true
├─ _judge_and_store_regime(trade_date)     # M1-1：读情绪行+指数趋势→规则判定→落库
├─ detect_and_store_themes(trade_date, top_n=3)  # M1-2：涨停聚类→Top3 落库
└─ backfill_regime(days=120)               # M1-1c：纯 SQL 聚合 breadth/量能 +
                                           #   provider 指数全量历史，情绪分映射近似
                                           #   （reason 标注"[回填近似]"）
```

## 4. API 端点（market_perception_async.py）

| 端点 | 用途 |
|---|---|
| `POST /api/market/perception/snapshot` | 每日快照（调度任务调） |
| `POST /api/market/perception/backfill-regime` | `{days:120}` 回填 |
| `POST /api/market/perception/detect-themes` | `{date:"2026-08-18"}` 回放验收 |
| `GET /api/market/regime?days=20` | regime 时间序列 |
| `GET /api/market/sentiment-history?days=20` | 情绪时间序列 |
| `GET /api/market/themes?date=` | 主线查询 |
| `PUT /api/market/themes/{id}` | LLM 回写 theme/catalyst/confidence（只允许这三字段） |

## 5. 表 DDL（已应用到生产，入库存档用）

三张表：`quant.market_regime`(trade_date PK, regime, index_trend_score, sentiment_score, volume_ratio, ad_ratio, reason)、`quant.market_sentiment_daily`(trade_date PK, up/down/flat_count, ad_ratio, new_high/low_count, volume_ratio, total_turnover, volatility, fear_greed_index, coverage, partial)、`quant.market_theme`(id PK, trade_date+rank UNIQUE, theme, sector, limit_up_count, stocks jsonb, fund_flow, catalyst, confidence)。完整 SQL 见 RFC 007 §3/§4/§5 的表结构定义，字段一致。

## 6. 工单台账与验收命令（2026-08-25 状态更新）

| 序 | 工单 | 验收命令 | 标准 | 状态 |
|---|---|---|---|---|
| 0 | settings.py 坏合并修复（§1） | §1 的验收脚本 + 后端重启成功 | 干净环境 import 通过；:5001 健康 | ✅ 完成（`2e3c6406`） |
| 1 | M1 代码重写（§2/§3/§4）+ 路由注册 | `curl -X POST localhost:5001/api/market/perception/snapshot` | 三步 stored=true | ✅ 完成（`90ed2b5c`+`45cf08e9`，16 单测 `4c73294e`） |
| 2 | M1-1 验收 | `curl "localhost:5001/api/market/regime?days=5"` | 每日 1 条含 reason | ✅ 完成（08-21/24/25 均为 trend_down） |
| 3 | M1-1c 回填 | `curl -X POST .../backfill-regime -d '{"days":120}'` 后查 COUNT | regime ≥120 条 | ✅ 完成（回填保护 `2ef93bd7`：ON CONFLICT DO NOTHING，不覆盖真实快照） |
| 4 | M1-3 验收 | `curl ".../sentiment-history?days=5"` | 字段完整，coverage≥4000 或 partial=true | 🟡 部分（仅 08-24/25 两天，coverage 450/2298 仍 partial——随每日调度自动积累） |
| 5 | M1-2a 验收 | `curl -X POST .../detect-themes -d '{"date":"2026-08-18"}'` | 落库 Top3 含农业相关板块 | ✅ 完成（8 条主线落库） |
| 6 | M1-2b 催化剂接线：agent 读聚类结果 → PUT 回写 theme/catalyst | 当日 theme 记录有 catalyst | 命名连续（传入近7日已有 theme 对齐） | 🟡 进行中（1/8 已回写，非阻断） |
| 7 | 调度挂载：**Agent OS scheduler**（见 §6.1） | 见 §6.1 验收 | 次日自动落库 | ✅ 完成（2026-08-25，任务 id `7f617ce3-0306-416f-b226-1b7092e9e69f`） |
| 8 | 合并 main + 更新 RFC 003/005 看板勾选 | — | — | 🟡 待办 |

### 6.1 调度挂载实现（2026-08-25，走 Agent OS——正确架构）

**架构决策**：调度任务**必须走 Agent OS scheduler**（postgres 持久权威注册表），**不是** quantsys-v2 本地 `scheduler_tasks` 表（那是后端内部数据任务，不驱动 agent）。投递链：

```
Agent OS scheduler（cron 触发）
  → 执行 command = scripts/os-remind-bridge.sh <task_name>
  → bridge 按任务名查 payload（prompt/window），写入 OS memory（tags: office:reminder:<window>）
  → lifecycle 插件 60s 轮询（memory.search tag=office:reminder:<window>）
  → agent.followup() 注入 investor 会话
  → agent 收到 prompt → 调用工具 → 执行 quantsys-v2 snapshot API
```

**任务定义**（与 `reminder_create` 工具等价的 API 调用，`POST /api/v1/scheduler/tasks`）：

```json
{
  "name": "market_perception_daily_snapshot",
  "owner": "investor",
  "cron": "0 30 15 * * 1-5",
  "command": "/Users/yunpeng/pi-investment/agent-dh/scripts/os-remind-bridge.sh market_perception_daily_snapshot",
  "payload": {
    "prompt": "【M1 每日快照】执行 market_perception_snapshot：调用 quantsys-v2 POST http://localhost:5001/api/market/perception/snapshot ...",
    "window": "w-51c8d482"
  },
  "enabled": true,
  "timeout": 60
}
```

**要点**：cron 必须是 **6 字段**（秒 分 时 日 月 周），5 字段会报 validation failed；bridge 脚本依赖 `AGENT_OS_URL`（默认 `http://localhost:8080`）——**Agent OS 后端必须保持运行**（`agent-os/bin/agent-os serve`，本次挂载时发现其未运行，已手动拉起）。

**验收**：
```bash
# 1. 任务可见
curl -s localhost:8080/api/v1/scheduler/tasks | python3 -m json.tool | grep -A2 perception
# 2. 链路测试：手动触发 → bridge 入信箱
curl -s -X POST localhost:8080/api/v1/scheduler/tasks/7f617ce3-0306-416f-b226-1b7092e9e69f/trigger
# 3. 信箱落痕
curl -s "localhost:8080/api/v1/memory?limit=5" | grep reminder
```

✅ 2026-08-25 已验证 1-3 全部通过（trigger status=success，bridge 输出"已入信箱"，memory 有 reminder 记录）。

**⚠️ 运维依赖**：本任务触发后由 investor agent（w-51c8d482）收到 prompt 执行快照。若 DSH :13080 未运行或 lifecycle 轮询异常，提醒会滞留信箱——建议定期 `reminder_list` 检查任务健康，故障时查 `office:reminder:<window>` 信箱积压。

## 7. 操作警戒（血泪教训，必须遵守）

1. **修 settings 前禁止重启后端**（stale pyc 存活中）
2. **停止后端/实例走 stop.sh 精确停止**，禁止 pkill 模糊匹配（多实例铁律 2026-08-21 起）
3. **worktree 会被外部删除**——代码及时 commit 到分支，别留在工作区
4. agent-dh 侧若改 quantsys-v2-client：**pnpm file: 是硬拷贝**，改后必须 `pnpm install` 同步 `.pnpm` 存储再重启 DSH
5. 共享主工作区出现不属于自己的改动 = 停手信号（本仓库多会话并行）

## 8. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-21 | 创建。agent-dh 转入审计+文档角色；此前在 worktree 的实现代码因 worktree 被删丢失，关键模式与坑位完整保留于本文 |
| 2026-08-25 | 调度挂载完成（工单 7 ✅）：改为 Agent OS scheduler + bridge 投递链正确架构（§6.1），删除此前误插入 quantsys-v2 本地 `scheduler_tasks` 的错误记录；工单 0-5 完成状态已回填台账 |
