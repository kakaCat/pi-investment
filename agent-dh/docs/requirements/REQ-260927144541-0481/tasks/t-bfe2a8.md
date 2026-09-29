# t-bfe2a8 兼容收尾：老调用方不退化 + 工具面与流程文档同步·复核

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
兼容收尾：老调用方不退化 + 工具面与流程文档同步·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-09-27T11:16:48.392Z，窗口 9649f3da-188e-427b-a657-d7eaa76b6cbe）

设计与实现逐条对照（design/interfaces I-1~I-6 + 父卡 t8 计划项）：无行为性偏离；发现 4 处文档级/措辞级偏差（均已列明），另有 1 处越界说明（decompose-tools 预存在红与本设计无关）。

### 完成项

- I-1 reqboard_task_run：参数 task_id/requirement_id 与 10 个返回键与设计逐键一致；删除键 subtask_executed/blocked/stopped 确认「不再声明也不再返回」（probe + task-run-contract FR-2）→ 无偏离
- I-1 偏差①（文档级）：设计 I-1 的 errors 只列 DSH_JOBS_UNAVAILABLE/REQBOARD_DISPATCH_FAILED/REQBOARD_NO_BOUND_REQ，实现另发 REQBOARD_NOT_BOUND_TO_WINDOW 与 REQBOARD_TASK_NOT_FOUND（绑定与目标解析必需）——实现是声明的超集，属设计清单漏列，建议补齐接口文档 errors 行
- I-1 偏差②（措辞级）：设计写「二者至少一个」，实现更宽松——都不传时回落本窗口绑定需求，未绑定才报 NO_BOUND_REQ（probe I-1c）。行为更宽松且不违反硬约束，但设计自述与实现不一致（I-3 已写明缺省语义，I-1 未写）
- I-2 reqboard_task_execute：保留工具名 + 描述标「已弃用」；实现复用同一 factory（非「逐行委托」字面写法），parameters/output.schema/timeoutMs 逐字一致、12 声明键同集、execute 为同源新闭包——偏差③属机制措辞差异，行为等价（probe I-2 + task-run-contract TC-3）
- I-3 reqboard_task_tree：参数/返回/错误码（NO_BOUND_REQ、TASK_NOT_FOUND、NOT_BOUND_TO_WINDOW）与设计一致；无子卡 note 语义由 task-tree.test 覆盖 → 无偏离
- I-4 reqboard_task_status：改读台账 lastRun/lastReport，workflow 键保留且内容=run 摘要；设计要求的「删除直连 fs 读 ## Workflow 解析」已落实——grep "## Workflow" src 无命中 → 无偏离
- I-5 reqboard_task_move：角色感知报错（域 TASK_STATUS 单点 role→合法边，MoveTask 加「reqboard_task_move 未执行：」前缀）；偏差④：设计文案「{role} 卡不允许」，实现为「父卡不允许」（TASK_ROLE_LABELS 直接拼接）——角色+合法边要素齐全，仅一字级措辞差异，task-move-role.test 绿
- I-6 契约门禁：走 output-contract(27) + tools-schema(40)，声明键⊇返回键、参数 DSL 形状、全工具构造（下限 ≥15 已满足）→ 无偏离
- 父卡 t8 计划项：①回归既有链路（advance-chain 8 / run-status-tool 4 / task-transition-guard 5 全绿）②别名等价与旧键兼容已核验并落文档 §5.1-5.2 ③文档同步落 §5.4 联调样例 → 无偏离
- 越界说明（非本设计偏离）：decompose-tools.test.ts 的 5 项红经干净 HEAD 复跑逐条同名，属测试与 reqboard_task_move 旧返回契约的既有脱节（REQ-2e9473 时代断言），与本设计 I-1~I-6 无关，按父卡口径「除预存在红外全绿」不记本需求账上

### 下一步

建议：design/interfaces.md 的 I-1 errors 行补 REQBOARD_NOT_BOUND_TO_WINDOW / REQBOARD_TASK_NOT_FOUND，并明确「都不传 task_id/requirement_id 时回落本窗口绑定需求」；I-2 措辞由「逐行委托」改为「复用同一 factory」。均非阻断项。

---
