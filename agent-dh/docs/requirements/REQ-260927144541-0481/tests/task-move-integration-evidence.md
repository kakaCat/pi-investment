---
requirement_refs: [FR-5]
---

# 接口联调记录：reqboard_task_move 角色感知报错 + acceptance 接线（FR-5 / 设计 I-5）

> 执行时点：2026-09-27 18:38–18:40（CST）。执行窗口：`0b9d498f-1591-492a-a0aa-737209a04902`
> （Team Worker `reqboard-t-ac97a2` 的子卡 t-061657）。全部为**线上工具实调返回原文**，非应然描述；
> 调用均走**无副作用分支**（错误在 mutate 抛错回滚或写库之前返回），未改动任何台账状态。

## 一、联调环境（可复核）

| 项 | 值 | 来源 |
|---|---|---|
| 服务 | node PID **88697** LISTEN 127.0.0.1:13080，uptime 1464s → 启动约 18:16:16 | `lsof -nP -iTCP:13080 -sTCP:LISTEN` + self_status（18:40:40） |
| 线上产物 | `packages/web/dsh-pmboard/dist/index.mjs`，构建于 **2026-09-27 17:42** | `ls -la dist/index.mjs` |
| 产物含 FR-5 代码 | `amendTaskAcceptanceIfRequested` ×3、`该角色合法边`、`legalEdgesFor`、`父卡` 均命中 | `grep -c/-o … dist/index.mjs` |
| 调用窗口绑定态 | `reqboard_status` → **bound=false, open_count=0**（本 Worker 窗口未绑定 REQ-260927144541-0481） | reqboard_status 实时，18:38 |
| 结论前提 | 服务加载的是**含 FR-5 的 dist**（17:42 构建 → 18:16 重启加载），故实测行为代表本卡交付后的线上行为 | 由上两行推出 |

## 二、请求样例 → 期望 → 实际（I-5 契约）

| # | 请求（reqboard_task_move） | 期望（design/interfaces I-5 + test-cases TC-10/11） | 实际返回（原文摘） | 判定 |
|---|---|---|---|---|
| L1 | `{}` | 参数非法 → `REQBOARD_INVALID_INPUT`（工具壳先拦） | `success:false, task_id:"", error:"reqboard_task_move 未执行：至少给出 to 或 acceptance", code:"REQBOARD_INVALID_INPUT"` | ✅ |
| L2 | `{task_id:"t-c65b1a"}` | 既无 to 也无 acceptance → 不静默当成功 | 同 L1（task_id 回填 `t-c65b1a`） | ✅ |
| L3 | `{task_id:"t-c65b1a", acceptance:"功能正常"}` | acceptance 被**真正消费**并过计划期可证伪门槛 → 空话被拒 | `reqboard_task_move 未执行（修订验收标准被拒）：计划任务 t-c65b1a 的验收标准是空话（"功能正常"）——必须可证伪：写清跑什么命令、看到什么算过（如"npx vitest run 全绿"、"详情页含 8 个进度点"）（REQBOARD_INVALID_INPUT）` | ✅ **证明 acceptance 已接线**（未接线时该键不会被消费，走不到 checkAcceptance） |
| L4 | `{task_id:"t-zzzzzz", acceptance:"命令：npx vitest run tests/x.test.ts → 看到 1 passed"}` | 合法 acceptance 通过门槛后进入台账查询；任务不存在 → `REQBOARD_TASK_NOT_FOUND` | `reqboard_task_move 未执行：任务 t-zzzzzz 不存在（REQBOARD_TASK_NOT_FOUND）` | ✅ 合法分支也被消费（越过 checkAcceptance 才到 task 查询） |
| L5 | `{task_id:"t-c65b1a", to:"in_review"}`（子卡角色，非法边） | 期望命中子卡角色报错（含「子卡」+ 合法边） | `reqboard_task_move 未执行：本窗口没有绑定中的需求（REQBOARD_NO_BOUND_REQ）` | ⚠️ 见 §四：窗口归属门在角色校验**之前**（MoveTask.ts:70-77），本窗口未绑定，请求停在归属门 |
| L6 | `{task_id:"t-ac97a2", to:"in_review"}`（父卡角色，非法边） | 期望命中父卡角色报错（含「父卡」+ 合法边） | 同 L5（REQBOARD_NO_BOUND_REQ） | ⚠️ 同上 |

## 三、零副作用核对

- L5/L6 走的是 `deps.repo.mutate` 内抛错路径 → 事务回滚，不落状态。
- 调用前后只读 `reqboard_task_status` 复核：`t-ac97a2` 维持 `in_progress`（progress 20），未被本次调用改动；
  `t-c65b1a` 的 `done`（progress 100）由**链在 dev 子卡汇报后自行推进**，非本次调用所致。
- 台账 JSON 无本次调用产生的 comment/version 变化（错误路径在写 comment 之前返回）。

## 四、覆盖缺口与落点（诚实登记，不当作通过）

**缺口**：FR-5 的「角色感知报错」在**本窗口**无法走线上正例/反例——`reqboard_task_move` 的
窗口归属门（MoveTask.ts:70-77 `openRequirementsFor`）先于 `roleOf`/`assertTaskTransition`，
而本 Worker 窗口未绑定任何需求，故只能返回 `REQBOARD_NO_BOUND_REQ`。

**已闭环的替代证据**（同一交付、确定性）：
- `tests/task-move-role.test.ts` TC-10：legacy 边推父卡（in_progress→in_review）→ 报错含「父卡」「合法边」「in_progress→in_review」，且状态零变化；
- 同文件：子卡（→testing）报错含「子卡」「合法边」；
- 领域文案由 `TaskStatus.ts` 单点产出，工具边界只补 `reqboard_task_move 未执行：` 前缀，live 与 test 走同一函数。

**补验建议**（若需线上覆盖）：由**已绑定 REQ-260927144541-0481 的窗口**重放 L5/L6 两条即可，
请求样例与期望已固化在上表；本卡不改归属门（越权改动会破坏 R-019 账户/窗口边界同类纪律）。

## 五、范围外观察（不动代码，供复核阶段判）

`src/http/routers/tasks.ts:109` 的看板人工流转路径调用 `transitionTask(task, to, {...})` **未传 role**
（缺省 legacy）→ 看板可把父卡/子卡推到 `testing/in_review`，而 agent 工具按角色拒绝。
二者语义分叉是否预期，属 FR-5 的**相邻面**、不在本卡范围，登记待复核。

## 六、复现命令

```bash
# 线上产物含 FR-5 符号（应分别输出 3 / 该角色合法边 / legalEdgesFor / 父卡）
cd agent-dh/packages/web/dsh-pmboard
grep -c 'amendTaskAcceptanceIfRequested' dist/index.mjs
grep -o '该角色合法边\|legalEdgesFor\|父卡' dist/index.mjs | sort -u

# 领域与用例的确定性回归
npx vitest run tests/task-move-role.test.ts tests/task-move-snapshot.test.ts tests/amend-acceptance.test.ts
```
