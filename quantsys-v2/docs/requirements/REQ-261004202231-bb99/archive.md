# 归档材料（REQ-261004202231-bb99）

> 用法：验收单全部通过 → 需求进入 `archived` → 用本文件的内容调
> `reqboard_submit(kind=archive)`（字段逐一对应）。**验收单未过时提交会被舞台门拒绝**
> （实测：`REQBOARD_BAD_STATUS：需求处于 accepting，只有已归档或历史完成的需求才能备归档材料`）。

## 一、需求目录

`quantsys-v2/docs/requirements/REQ-261004202231-bb99`

## 二、目录内文档清单（人读）

| kind | path |
|---|---|
| requirement | `requirement.md`（含 FR-1~FR-6 与范围变更记录） |
| plan | `decomposition.md`（9 卡计划 + 顺序修正注记） |
| verification | `verification.md`（验收单本体） |
| notes | `baseline.md`（删前基线）、`deletion-checklist.md`（逐文件清单 + 十一节实施证据） |
| notes | `design/architecture.md`、`design/data-model.md`、`design/interfaces.md`、`design/migration.md`、`design/test-cases.md` |
| notes | `reviews/self-review.md`、`tests/verification-evidence.md`（含 `covers:` 逐任务覆盖对照） |

**未列清单的（机器产物，已声明豁免）**：`queue.json`（看板任务台账，唯一存储）、
`rtm-*.yml` 与 `rtm-implementing/*.yml`（看板生成的追溯台账）。

## 三、合并去向（merged_into）

| 文档 | 承载了什么结论 |
|---|---|
| `docs/architecture/project-manual.md` | 记忆不在 v2（唯一后端 agent-os）+「返回 200 ≠ 在工作」这条教训 + agent-os 启动入口 |
| `quantsys-v2/docs/architecture/memory-subsystem-retired.md` | v2 侧下线的完整结论页（为什么删、删了什么、三条「删干净」判据、别误删清单） |
| `agent-dh/docs/architecture/memory-and-recall.md` | agent 侧记忆与召回的口径更新（原 recall_audit 章节改为下线说明） |
| `agent-dh/docs/work-logs/2026-10/agent-os-restore.md` | agent-os 本机重建的步骤、验证与四个坑（TCC、schema 漂移、goproxy、plist） |

## 四、一句话索引条目（index_entry）

> quantsys-v2 记忆子系统下线：15 个 `/api/memory*` 端点与领域/仓储/测试/端口全删，
> 记忆改由 agent-os（`:8080`）承载；表先备份后 DROP，四处外部消费方同步迁移。

## 五、说明书更新点（manual_updates）

| path | section | 这一节现在多了什么认知 |
|---|---|---|
| `docs/architecture/project-manual.md` | 最近更新（新知识从这里进来） | 新增 2026-10-05 行：记忆不再由 v2 承载（唯一后端 agent-os），并记下「返回 200 ≠ 在工作」 |
| 同上 | 2. 三层架构（谁负责什么） | 记忆不在 quantsys-v2：读写/审计/蒸馏由 agent-os 承担，v2 只保留数据与量化 |
| 同上 | 4. 怎么跑起来 / 5. 去哪儿找细节 | 补 agent-os 的启动命令（:8080，launchd），修掉早已不存在的 `start_all.py`，加上记忆下线与本机重建两处入口 |

## 六、交付提交

| 提交 | 内容 |
|---|---|
| `824bc960` | v2 侧下线（89 文件 / +3,631 −5,029） |
| `313111a6` | agent-ts 记忆消费迁 agent-os（15 文件 / +360 −1,322） |
| `cf9c8549` | 需求文档补 t9 结果与测试写法备忘 |
| `ba59a9d9` | 说明书更新点（记忆不在 v2） |
