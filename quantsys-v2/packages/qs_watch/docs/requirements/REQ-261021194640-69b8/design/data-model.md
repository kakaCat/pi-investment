---
title: 盯盘执行闭环三接缝 · 数据模型与迁移（REQ-261021194640-69b8）
status: draft
owner: agent（本窗口）
reviewers: 投资人
prd: docs/requirements/REQ-261021194640-69b8/requirement.md
serves: FR-3, FR-7
created: 2026-10-21
updated: 2026-10-21
---

# 盯盘执行闭环三接缝 · 数据模型与迁移  serves: FR-3, FR-7

## 摘要  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **问题**：消息待办没有证据字段，无法追溯「哪条消息让它建单」；统计只能扫全表。
- **方案**：`watch_todos` 加一列可空 `evidence jsonb` + 一个部分索引；其余表全部复用，不新增事实源。
- **影响面**：一张表、一条迁移、一个仓储文件；旧数据零回填，回滚只丢证据。

## 背景与问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 需求来源  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-3 | 消息待办要可追溯 | `evidence` 落消息摘要/命中词/告警 id |
| FR-7 | 统计要能读 | 复用台账列与触发证据，不建新表 |
| FR-1 | 成交回写要有证据 | 复用 `watch_triggers.detail.exec`，不加列 |

### 现状与代价  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

`watch_todos` 只有 symbol/account/level/终端字段，没有载荷；消息待办建出来后无法回答「因为哪条消息」。执行时延散落在触发 JSONB 里，统计要全表扫描；无索引时消息去重查询随待办增长变慢。

### 为什么是现在  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

表结构一旦被实施代码依赖就难改；在拆分前把列与索引定死，实施只写 SQL 与读写口径。

## 目标与非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 迁移幂等：重复执行零行变更。
- 兼容：缺列库上旧代码照常启动与判定（fail-open）。
- 可回滚：单条语句可恢复，且不破坏业务数据。

### 非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 不新建表、不改既有列类型与约束。
- 不回填历史待办证据（历史消息待办为空属事实）。
- 不引入事件表/outbox（成交量级低，同步回调足够）。

## 方案总览  serves: FR-3, FR-7

```text
watch_todos
  + evidence jsonb NULL          ← 消息证据（来源/标题/命中词/告警 id）
  + idx (symbol, action_kind) WHERE terminal IS NULL   ← 未收敛去重查询
watch_triggers.detail.exec       ← 执行时延（既有，不改）
watch_rule_changes               ← 规则变更审计（既有，不改）
watch_receipts                   ← 超时回执（既有 kind，无 CHECK）
```

**关键概念**：证据（evidence）是待办的只读附带信息，不参与状态机；时延（detail.exec）以触发为事实源，不复制到待办。

## 架构与依赖  serves: FR-3, FR-7

- **写入方**：消息桥建单时写 `evidence`；无其它写入方。
- **读取方**：待办接口序列化、统计聚合、复盘查询。
- **依赖**：迁移只依赖 PostgreSQL 11+（部分索引与 jsonb 均支持）。
- **降级**：OR M 缺列预检失败时，读路径返回 None、写路径忽略该字段并告警。

## 数据模型  serves: FR-3, FR-7

### 实体与字段  serves: FR-3, FR-7

| 实体 | 字段 | 类型 | 可空 | 默认 | 约束/说明 |
|---|---|---|---|---|---|
| `quant.watch_todos` | `evidence` | jsonb | 是 | NULL | 消息证据对象；不参与状态机 |
| （既有） | `terminal` | varchar(16) | 是 | NULL | handled/ignored/expired |
| （既有） | `action_kind` | varchar(24) | 是 | NULL | trade/rule_change/observe |
| （既有） | `symbol` / `account` / `level` / `due_at` | 同现状 | — | — | 不改语义 |

`evidence` 形状（advisory，读侧按 dict 容错）：

```json
{"source": "news|policy", "tier": "critical", "alert_id": 123,
 "titles": ["..."], "words": ["减持"], "scanned_at": "2026-10-21T16:30:00+08:00"}
```

### 约束与不变量  serves: FR-3, FR-7

- `evidence` 只增不改（待办收敛后不再写）。
- 不新增 CHECK：证据是附注，不因字段缺失阻断建单。
- 唯一性仍由既有主键与状态机保证；不做 (symbol, action_kind) 唯一约束（历史待办会冲突）。

### 迁移与回填  serves: FR-3, FR-7

- 迁移文件：`infrastructure/persistence/migrations/20261021_watch_todos_evidence.py`
- 默认 dry-run：打印将执行的 SQL 与预估行数；`--apply` 才写库；`--dsn` 可显式指定。
- 步骤：① `ALTER TABLE quant.watch_todos ADD COLUMN IF NOT EXISTS evidence jsonb`；② `CREATE INDEX IF NOT EXISTS idx_watch_todos_open_symbol_action ON quant.watch_todos (symbol, action_kind) WHERE terminal IS NULL`。
- 回填：无。历史待办 `evidence` 保持 NULL，读侧按「无证据」展示。
- 幂等：两条语句均带 IF NOT EXISTS，重跑零行变更。

### 生命周期  serves: FR-3, FR-7

- 随待办归档保留；自动过期（3 天）只改 `terminal`，不删行，证据随之保留。
- 清理：纳入既有待办留存策略，本设计不新增清理任务。

## 接口设计  serves: FR-3

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-7 | 数据契约 `watch_todos.evidence` | 证据对象（见上） | 读侧 dict 或 None | 非法 JSON 由 DB 拒绝；读侧解析失败按 None 并告警 | 可空列，additive |
| IF-8 | 迁移脚本 CLI | `--apply` / `--dsn` / 缺省 dry-run | 打印 SQL 与行数；退出码 0/2 | 连接失败退出码 2，不写库 | 新脚本，无调用方 |

#### IF-7 证据字段契约  serves: FR-3

**语义**

消息待办建单时写入一份只读证据；待办接口返回 `evidence` 字段（无则 null）。它回答「为什么建这条待办」，不参与任何判定分支。

**错误码**

无接口错误码。写侧：非可序列化对象在应用层被拒绝（ValueError），事务回滚；读侧：坏 JSON 由 DB 保证不会写入，解析异常退化为 None 并记日志。

**兼容性**

可空列；旧代码不读写该列，行为不变。缺列库上读写降级（读 None / 写忽略 + 告警）。

#### IF-8 迁移脚本  serves: FR-3

**语义**

一次性运维入口：默认 dry-run 只打印计划；`--apply` 执行加列与建索引；`--dsn` 覆盖连接串。

**错误码**

| 情形 | 退出码 | 处理 |
|---|---|---|
| 连接失败 | 2 | 检查 DSN，不重试写库 |
| SQL 失败 | 2 | 事务回滚，保留错误原文 |
| 正常（含 dry-run） | 0 | 读回执确认 |

**兼容性**

新脚本，不被应用代码调用；生产与测试库各执行一次。

## 备选方案  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| 什么都不做 | 用 close_reason 拼消息摘要 | 零迁移 | 建单前无证据、不可查询、被覆盖 | 追溯性丢失 |
| 新建消息待办关联表 | 独立 evidence 表 | 结构规范 | 多一张表与一次 join | 一列 jsonb 足够，YAGNI |
| 复用 context/action_params 列 | 塞进既有 JSONB | 不加列 | 语义污染治理字段，读侧歧义 | 会与规则注记混淆 |

## 四风险与证据  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 没有证据字段能否排查消息待办来源？ | 现表无载荷，生产消息待办尚未产生 | 需要 |
| 可用性 | 加列会不会锁表？ | PostgreSQL 加可空列是元数据操作；表规模千级 | 低风险 |
| 可行性 | 部分索引是否被查询用上？ | 去重查询条件与索引前缀一致 | 可行 |
| 商业可行性 | 迁移与回滚成本？ | 两条 IF NOT EXISTS 语句 | 可接受 |

## 失败模式与回滚  serves: FR-3

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 迁移中断 | 连接断开/锁等待超时 | 列或索引只建一半 | 迁移退出码与回读 information_schema | 重跑幂等语句 | 值班 |
| 缺列库启动 | 未执行迁移 | 证据读 None，其余照常 | 启动日志列预检告警 | 补跑迁移 | 值班 |
| 索引膨胀 | 长期未清理 | 写变慢 | 索引大小监控 | 重建索引 | 值班 |
| 证据写入失败 | 非法对象 | 建单失败（消息无待办） | 桥返回 errors | 修正入参后重扫 | 值班 |

## 跨关注点  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 证据不含凭证与个人信息 | 只存标题与命中词，不存原文全文 |
| 性能 | 加列不影响既有查询；索引服务去重 | 部分索引只覆盖未收敛行 |
| 可观测 | 迁移与缺列都有日志 | 预检告警 + 迁移回执 |
| 兼容 | 旧库/旧代码双兼容 | 可空列 + 读侧 None + 写侧忽略 |

## 交付拆分与里程碑  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 迁移 | 加列 + 部分索引 | dry-run 与 apply 均退出码 0，重跑 0 行 | agent | 2026-10-22 |
| M2 读写口径 | ORM 映射 + 仓储读写 + 缺列降级 | 缺列库用例绿 | agent | 2026-10-22 |

## 需求追溯  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-3 | 数据模型 / IF-7 | 建单后 evidence 可读 | 证据缺失率 0 |
| FR-7 | 数据模型 | 统计聚合不带全表扫描 | 查询 < 200ms |
| FR-1 | 数据模型（复用 detail.exec） | 时延可读 | 时延字段非空率 |

## 常见问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 回答 |
|---|---|
| 为什么用 jsonb 而不是多个列？ | 证据形状会随消息源变化，jsonb 免迁移；查询只按 symbol/action_kind，不需要列级索引。 |
| 为什么不给 evidence 加 NOT NULL？ | 历史待办与其它来源待办没有证据，强制非空会阻断建单。 |
| 部分索引为什么不带 due_at？ | 去重查询按 symbol+action_kind+terminal，due_at 不参与过滤。 |
| 迁移失败会不会留下半成品？ | 单事务内执行，失败整体回滚；IF NOT EXISTS 保证重跑安全。 |
| 回滚要不要删列？ | 可选：删列会丢证据但不影响业务；生产回滚优先只停用读写。 |
| 需要回填历史数据吗？ | 不需要：历史待办没有消息来源，回填只能造假。 |
| 与 watch_rule_changes 的关系？ | 独立表：前者记待办证据，后者记规则变更审计，不合并。 |

## 开放问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 证据是否需要保留原文链接 | 只存标题 / 加 url | agent（实施时定） | 2026-10-22 |
| 索引是否需要 CONCURRENTLY | 普通建 / 并发建 | agent（按表规模定） | 2026-10-22 |

## 附录  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 现有表结构：`infrastructure/persistence/orm/models/watch_todo.py`
- 迁移风格参考：`infrastructure/persistence/migrations/20261021_watch_rules_position_interval.py`
- 架构与接口：`design/architecture.md`、`design/interfaces.md`
