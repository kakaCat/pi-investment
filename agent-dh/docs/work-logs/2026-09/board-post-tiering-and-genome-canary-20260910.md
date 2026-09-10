# 公告板发帖分档（R-015 v15）+ 基因组金丝雀修复（2026-09-10）

- 角色：investor | 窗口：w-50fc8c52
- 需求：REQ-da85cb（chore）——用户选定方案 C「放宽 R-015」
- 结论：工具层已改（分档门禁 + 防噪声护栏），并顺带定位并修复了一个**阻塞基因组进化约 2 天的根因**（DSH 提示词组装层：金丝雀无作用域组装取不到 agent 级变量）。

## 一、需求：公告板发帖分档（R-015 v15）

用户背景：公告板当时看起来"空了"（诊断结论：60 帖全部终态，0 个 open，页面默认停在悬赏池标签，非故障）。
随后用户问"是不是 memory 该走公告板还是两者都走"，并在三选一中选定 **C：放宽 R-015**。

分档规则（已写入规则段，见 R-015 v15）：

| 档位 | needs_action | 进池状态 | 确认要求 |
|---|---|---|---|
| ①悬赏档 | true | open（悬赏池） | 必须先 ask_user_question，用户同意后带 confirmed=true |
| ②纯记录档 | false | done（终态） | 免确认，可直接落台账 |

配套工具层改动 `packages/lifecycle/src/board-tools.ts`：

1. `confirmed` 门禁从"一刀切"改为仅对悬赏档生效（needs_action=true 且无 confirmed → 返回 `needs_user_confirmation`，不触达后端）。
2. 纯记录档新增**防噪声护栏** `isNoisePost()`：标题形如 `reminder …delivered` / `auto-track…` / 正文 < 20 字 → 返回 `rejected_noise`。
   依据：2026-09-05 公告板清理删掉的 20 帖中 10 帖是 `reminder * delivered` 类系统噪声。
3. 工具描述同步重写（分档语义 + 日常复盘流水仍走 memory_write）。

测试：`packages/lifecycle/tests/board-post-gate.test.ts`（新增，8 例全绿）；`tests/plugin-schema.smoke.test.ts` 19 例全绿。
构建：`packages/lifecycle` → `dist/index.mjs`（2026-09-10 20:57）。

## 二、顺带发现并修复：基因组写入自 2026-09-08 22:45 起全部失败

**症状**：`genome_update` 返回
`渲染金丝雀失败，已自动还原到 v14。错误: prompt variable "{{model}}" has no value for this assembly (section "deployment:persona")`。

**根因（已核实）**：
- 金丝雀 `packages/genome/src/index.ts: canaryRender()` 原用**无作用域** `ctx.systemPrompt.assemble()`；
- 而 investor 的 agent 预设 persona 文本含 `{{model}}` / `{{cwd}}`（`~/.dsh-agent-dh/.agent-presets/investment/agent.cordis.yml`），这两个变量由 **agent 作用域**的变量提供者注册；
- 无作用域组装取不到它们 → 渲染必然抛错 → 每次写入都被自动还原。
- 时间线佐证：GENOME 历史最后一条成功写入 = **2026-09-08T05:40:02Z**（rules v14）；agent 预设文件 mtime = **2026-09-08 22:45**（本地）→ 预设上线后基因组再无新版本，规则/教训进化被静默冻结约 2 天。

**修复**：金丝雀改为与 agent-loop 生产路径同款组装 `assemble({ agent, scope: agent })`（即 dsh-agent 的 `assembleContextFor(agent)` 返回形状，已核对 `node_modules/@deepseek-ai/dsh-agent/lib/index.js:384-390`）；agent 通过惰性 `ctx.inject(['agents'])` + `agents.roots()` 解析（同 bulletin 页面模式），取 id 前缀匹配配置 `agentId`（默认 investor）的 root，退化取第一个；取不到 agent 时退回无作用域组装。

## 三、验证证据（R-013 数据来源标注）

| 数据 | 值 | 来源与时点 |
|---|---|---|
| 公告板帖数与状态分布 | done 36 / dropped 24 / open 0 | `board_read(status=all)` + `curl /api/v1/board/posts`，2026-09-10 20:46 |
| 基因组最后成功写入 | rules v14，2026-09-08T05:40:02Z | `genome_history`，2026-09-10 20:55 |
| 分档门禁测试 | 8/8 通过 | `vitest run packages/lifecycle/tests/board-post-gate.test.ts`，2026-09-10 20:57 |
| schema 冒烟 | 19/19 通过 | `vitest run tests/plugin-schema.smoke.test.ts`，2026-09-10 20:59 |

## 四、重启后验证结果（2026-09-10 21:00-21:05，全部通过）

1. **金丝雀修复生效**：`genome_update(rules, expected_section_version=14)` 成功 → rules **v14→v15**、genome **g25→g26**、git commit `addac86`（此前同样的调用必被金丝雀失败自动还原）。
2. **公告板两档门禁活体实测**（重启后新 dist）：
   - 档②纯记录免确认 → 真落库：`post_id=db4783da-d4f3-46a2-ac43-588d2aead1ab`，`status=done`；
   - 档①悬赏无 confirmed → `status=needs_user_confirmation`，未落库（`post_id=`空，受控探针）；
   - 防噪声护栏 → `status=rejected_noise`，未落库（探针标题 `reminder … delivered`）。
3. **留痕**：`decision_audit(record)` → `DEC-20260910210052-90744e90`（type=rule_change, entity=rules:R-015）；`memory_write(experience)` → `618597e1-c4e9-488c-a27e-103527ba65ec`。
4. **归档**：逐文件提起（不夹带其他窗口改动）→ main `67e43a0a`（本文件 + board-tools.ts + genome/src/index.ts + board-post-gate.test.ts）。

## 五、遗留问题（需人工/其他窗口处理）

1. **R-010 无法执行**：`:13080` 实例的 `cordis.patch.yml` 未注册 notification 插件（`@pi-investment/notification`），`feishu_notify`/`notification_send` 在本会话工具集中不存在（`Object.keys(tools)` 126 项中无匹配）→ 本次里程碑通知未发出，规则 R-010 目前是"无工具可调"状态。
2. **检查点夹带**：重启检查点分支 `agent-self/20260910-210017` 除本任务 4 个文件外，还提交了**其他窗口（w-8f2c4cc5，REQ-2057bd）20:56-20:58 的未提交改动**（`packages/pages/execution` 的 client/board-mount/styles/view + lib 产物）。已刻意**不**合回 main，原样保留在该 wip 分支，待其归属窗口自行提交/合并。

