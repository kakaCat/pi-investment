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

## 四、待办（重启后执行）

1. `genome_update(rules, expected_section_version=14)` 落 R-015 v15（金丝雀修复后应可成功）。
2. 活体验证公告板两档：纯记录档免确认真发；悬赏档无 confirmed 被拦。
3. `decision_audit(record)` + `memory_write` 留痕；R-010 里程碑通知（feishu_notify）。
4. 验证通过后 `self_finalize(merge)` 合回 main。
