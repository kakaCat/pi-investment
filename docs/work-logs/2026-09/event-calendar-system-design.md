# 事件日历系统设计与实现（E1）

**版本**: v1.0
**日期**: 2026-09-01
**实现者**: investor (w-5b8aac2a)
**配套设计**: [每日固定动作体系设计](./daily-routine-system-design.md) 第六章（特殊日子）

---

## 一、决策：为什么建在 quantsys-v2 数据库

| 方案 | 判断 | 理由 |
|---|---|---|
| **quantsys-v2 `quant.event_calendar` 表** | ✅ **采用** | 单一真相源（宪法§5 数据驱动）；调度器任务与 Agent 工具共用查询；与 watch_rules 同级先例一致；可关联历史行情做事件影响回测 |
| 配置文件/JSON | ❌ | 不可动态查询、Agent 工具无法直接调、多人编辑冲突 |
| 内嵌调度任务 payload | ❌ | 每事件一任务不灵活，无法查"未来 N 天事件" |

事件日历是**市场日历数据**，本质是数据资产，入库是正确架构。

---

## 二、表结构设计

```sql
CREATE TABLE IF NOT EXISTS quant.event_calendar (
  id            serial PRIMARY KEY,
  event_type    varchar(32) NOT NULL,          -- cpi/ppi/pmi/gdp/nbs/lpr/fomc/us_cpi/nfp/earnings/futures_delivery/policy/other
  event_date    date NOT NULL,                 -- 事件日期
  event_time    time,                          -- 发布时刻（如 09:30），NULL=盘中/全天
  title         varchar(200) NOT NULL,         -- "8月CPI发布"
  description   text,                          -- 预期值/前值/背景说明
  symbol        varchar(20),                   -- 关联标的（财报/交割/解禁用），宏观事件为 NULL
  market        varchar(8) DEFAULT 'CN',       -- CN/US 等
  importance    smallint DEFAULT 1,            -- 1低 2中 3高（FOMC/CPI/GDP=3，LPR/PMI=2）
  status        varchar(16) DEFAULT 'pending', -- pending/notified/collected/reviewed/skipped
  source        varchar(50),                   -- nbs/fed/pboc/exchange/manual/akshare
  meta          jsonb,                         -- 扩展：预期值/前值/采集结果/影响评估
  created_at    timestamp DEFAULT now(),
  updated_at    timestamp DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_event_calendar_date   ON quant.event_calendar (event_date);
CREATE INDEX IF NOT EXISTS idx_event_calendar_status ON quant.event_calendar (status) WHERE status IN ('pending','notified');
CREATE INDEX IF NOT EXISTS idx_event_calendar_type   ON quant.event_calendar (event_type);
```

**设计要点**：
- `event_type` 枚举化，便于按类型过滤和分类处理
- `status` 状态机：pending（待发生）→ notified（已预警）→ collected（已采集）→ reviewed（已复盘）；skipped（跳过，如节假日顺延调整）
- `meta` JSONB 存扩展（预期值、前值、实际值、采集结果链接），灵活不破坏结构
- `symbol` 可空——宏观事件为 NULL，财报/交割/解禁带标的代码
- 索引覆盖"未来 N 天待处理事件"的核心查询

---

## 三、API 设计（/api/events）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/events` | 查日历：?start=&end=&type=&status=&symbol=&days_ahead=N（默认未来7天） |
| POST | `/api/events` | 建事件（手动/初始化脚本） |
| PATCH | `/api/events/{id}` | 更新状态/结果/影响评估 |
| DELETE | `/api/events/{id}` | 删除事件 |
| GET | `/api/events/upcoming?days=2` | 快捷查"未来N天待处理事件"（每日检查任务核心调用） |

**契约**（与现有 API 一致）：成功 `{'success': True, 'events': [...]}`；失败 `{'success': False, 'error': ...}` + error_response 400/404。

---

## 四、2026 年已知事件初始化数据

### FOMC 2026（官方日程，importance=3）
| 日期 | 事件 | 备注 |
|---|---|---|
| 2026-01-27/28 | FOMC 第1次会议 | |
| 2026-03-17/18 | FOMC 第2次 | 附点阵图 |
| 2026-04-28/29 | FOMC 第3次 | |
| 2026-06-16/17 | FOMC 第4次 | 附点阵图 |
| 2026-07-28/29 | FOMC 第5次 | |
| 2026-09-15/16 | FOMC 第6次 | 附点阵图 |
| 2026-10-27/28 | FOMC 第7次 | |
| 2026-12-08/09 | FOMC 第8次 | 附点阵图 |

> FOMC 为两天会议，决议在北京时间次日 02:00 公布，事件日历以第二天（决议日）为准，importance=3，带点阵图的季度会议影响最大。

### 国内宏观（统计局官方日程，CPI/PPI importance=3、PMI/GDP importance=2）
| 类型 | 发布节奏（每月） |
|---|---|
| CPI/PPI | 1/9、2/11、3/9、4/10、5/11、6/10、7/9、8/9、9/9、10/14、11/9、12/9（9:30） |
| PMI | 每月末日（9:30） |
| 国民经济运行 | 1/19、3/16、4/16、5/18、6/16、7/15、8/17、9/15、10/19、11/16、12/15（10:00） |
| LPR | 每月 20 日（9:15），节假日顺延 |

### 交割日（每月规则）
| 类型 | 规则 |
|---|---|
| 股指期货交割 | 每月第三个周五 |
| ETF 期权交割 | 每月第四个周三 |

---

## 五、任务集成

| 任务 | cron | 动作 |
|---|---|---|
| `event-calendar-check` | `45 16 * * *`（每日16:45） | 调 `/api/events/upcoming?days=2` → 有事件则飞书预警 + 持仓影响预案 |
| `event-cpi-ppi` | `35 9 9-14 * *`（每月9-14日9:35） | CPI/PPI 采集 + 通胀判断（覆盖发布窗口） |
| `event-pmi` | `35 9 28-31 * *`（月末窗口） | PMI 采集 + 景气判断 |
| `event-lpr` | `20 9 18-23 * *`（20日±3天窗口） | LPR 采集（覆盖顺延） |
| `event-earnings-check` | `40 16 * 1,4,7,8,10 *`（财报季16:40） | 持仓股披露预警（1/4/7/8/10月为财报季） |
| `event-futures-delivery` | `20 9 * * 5`（每周五，内部再判断第三周五） | 交割日提示 |

> 月内相对固定的事件用 cron 窗口覆盖；FOMC/财报/两会等完全不定的事件靠 `event-calendar-check` 每日查表兜底。

---

## 六、实施步骤（本次执行）

1. ✅ 设计文档（本文件）
2. ✅ 建表 `quant.event_calendar`（14 字段 + 4 索引）
3. ✅ 仓储层 `event_calendar_repository.py`（EventCalendar ORM + list_upcoming/list_range/upsert/mark_status）
4. ✅ API 路由 `events_async.py`（6 端点）+ main.py 注册
5. ✅ 初始化 2026 年已知事件 **67 条**（FOMC 8 + CPI/PPI 12 + PMI 12 + 国民经济 11 + LPR 12 + 交割 12）
6. ✅ 每日检查任务 `event-calendar-check`（16:45，payload 投递盘后例程窗口 w-29882338）

---

## 七、验收记录（2026-09-01）

| 验证项 | 结果 |
|---|---|
| 建表 + 4 索引 | ✅ event_calendar created |
| 仓储 + 路由导入 | ✅ 6 路由：`/api/events/upcoming`、`/api/events`（GET/POST）、`/api/events/{id}`（GET/PATCH/DELETE） |
| 服务重启加载 | ✅ health_ok（pid 42304） |
| upcoming?days=30 | ✅ 6 条（9/9 CPI、9/15 国民经济、9/16 FOMC、9/18 交割、9/20 LPR、9/30 PMI） |
| 范围查询 fomc 9月 | ✅ 1 条（9/16 02:00） |
| PATCH 状态机 | ✅ pending→notified→pending 回滚，meta 合并正常 |
| POST 幂等 upsert | ✅ 重复创建更新同一条 id=6，总数稳定 67 无重复 |
| event-calendar-check 任务 | ✅ 已注册（cron `0 45 16 * * *`，payload 含 prompt+window） |

**遗留/后续**：
- 财报季持仓标的预约披露日未入库（需逐个查交易所预约表，标的驱动）
- FOMC/财报等不定事件的实际发布值采集回填机制（事件当日由检查任务触发采集动作）
- LPR 节假日顺延处理（cron 窗口兜底 + 检查任务日历兜底）

**通知**：feishu log_id 54e75f4c-98bb-4423-90dd-d607f0c24d26（reports）

---

## 八、配套实现补全（2026-09-01 追加）

用户指出"建了日历表，对应实现要设计吗"——补全 Agent 侧工具化闭环（原检查任务用 curl 裸调，不符合工具化架构）：

### 完整数据流（闭环）

```
quant.event_calendar 表（数据层）
  ↓ ORM
event_calendar_repository.py（仓储层）
  ↓ FastAPI
events_async.py /api/events（API 层）
  ↓ HTTP
quantsys-v2-client（TS 客户端层）— getUpcomingEvents/listEvents/getEvent/upsertEvent/updateEvent/markEventStatus/deleteEvent
  ↓ DSH 工具
event_calendar_check（Agent 工具层，investment 插件）
  ↓
Agent 决策 / event-calendar-check 调度任务（16:45）
```

### 补全清单

| 层 | 产出 | 验证 |
|---|---|---|
| TS 类型 | `types.ts` 追加 CalendarEvent/EventListRequest/EventUpsertRequest/EventListResponse | ✅ tsdown build 通过 |
| TS 客户端 | `client.ts` 7 个方法 + unwrap 扩展 3 个响应模式（events/event/deleted） | ✅ 构建通过 |
| Agent 工具 | `event_calendar_check`（investment 插件，upcoming/range 双模式） | ✅ schema 冒烟测试 19/19 通过 |

### 端到端验证
- `getUpcomingEvents(7)` = 0（9/1-9/8 空窗，正确）
- `getUpcomingEvents(10)` = 1（覆盖 9/9 CPI，正确）
- `listEvents(fomc, 9-12月)` = 3（9/16、10/28、12/9，正确）

### 产出文件
- `quantsys-v2-client/src/types.ts`（追加 4 个接口）
- `quantsys-v2-client/src/client.ts`（追加 7 方法 + unwrap 3 模式）
- `agent-dh/packages/investment/src/tools/EventCalendarTool/{prompt,EventCalendarTool,index}.ts`
- `agent-dh/packages/investment/src/index.ts`（注册第 9 个工具）

**说明**：Agent 工具走 tsx 直载（TS 源码即生效），但检查任务的 prompt 已可改用 `event_calendar_check` 工具替代 curl——任务下次触发时 Agent 会优先用工具。
