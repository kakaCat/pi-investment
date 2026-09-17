# REQ-422af1 实施文档（implementing 阶段）

> 阶段：implementing · 窗口 w-41e7e4cd · 依据：已批准 plan.md + 已确认 decomposition（12 卡）
> 决策补充：D-13（节点即选择器、无匹配）、D-14（vendor superpowers v6.3.0 / b36e082 / MIT）；heavy 范围 = **主 skill 全文 + 附属按需**

## 1. 实施顺序（严格串行，前一步不过不进下一步）

    S0 读卡：reqboard_task_move(t1, in_progress) 取卡全文，确认与本文一致
    S1 t1 冻结基线快照        ← 一切等价性的对照物，必须最先做
    S2 t2 分片库骨架 + 生成器/同步门禁
    S3 t3 路由解析 + 预算     ← 纯函数，可 TDD
    S4 t4 P0 落位 + 注入点切换 + 删直取   ← 等价门在这；不过则回滚，不进 P1
    S5 t5 六条门禁 + 故障注入
    S6 t6 注入留痕            ← 此后 P3 依赖它
    S7 t7 六节点两档（heavy=vendor 原文）+ 要素门禁
    S8 t8 类型档（六节点 × 六类型）
    S9 t12 文档同步（可与 S7 并行）
    S10 t9 surface 替换执行模型   ← 风险最高，独立验收
    S11 t10 结算点接入（默认关）
    S12 t11 看板可见 + 客户端重建

**依赖链**：t1→t4；t2→t3→{t4,t5,t6}；t4→t7→{t8,t12}；t6→t9→t10；t6→t11。

## 2. 每步的验证方式（照跑，不看印象）

| 步 | 验证命令/动作 | 通过判据 |
|----|--------------|---------|
| S1 | node scripts/dump-stage-prompts.mjs 连跑两次 + git log | diff 为空；快照早于取词改动 |
| S2 | node scripts/inline-prompt-fragments.mjs 后再 check；改 md 不生成 | 正常 0；故障注入 1 |
| S3 | npx vitest run tests/prompt-router.test.ts | 五种命中层级 + 6×2×6 无空串 + 去重 + 超限标记 |
| S4 | npx vitest run tests/prompt-baseline.test.ts tests/stage-prompts.test.ts；tsc；grep 直取 | 逐字一致 + 既有断言未改全绿 + 0 错误 + 0 命中 |
| S5 | npx vitest run tests/prompt-gates.test.ts + 六次故障注入 | 正常全绿；六条各自能红（记录注入方式） |
| S6 | npx vitest run tests/prompt-injection-log.test.ts | 十字段一致 + 有界 + 缺文件不抛 |
| S7 | npx vitest run tests/prompt-tiers.test.ts | 六节点两档不同 + heavy 与 vendor 原文逐字一致 + light < heavy |
| S8 | npx vitest run tests/prompt-categories.test.ts | 类型文本不同 + 各类型关键词命中 + 无孤岛 |
| S9 | python3 agent-dh/scripts/wiki_probe.py + 路径存在性核对 | 无死链；0 悬空引用 |
| S10 | npx vitest run tests/isolate-node-context.test.ts | 五条断言（T24-T28） |
| S11 | 同上（开关关/开两态） | 关=0 次调用；开=1 次 + 留痕 |
| S12 | pnpm build:client + verify-client-build.mjs | 哨兵通过；lib/client.js 新于 src |

**全局门禁**（每步结束都跑）：npx vitest run（包内）+ npx tsc --noEmit -p packages/pages/dsh-pmboard/tsconfig.json + 四条既有机械门禁（layer-boundary / size-budget / typecheck / message-hygiene）。

## 3. 实施纪律（本仓血泪）

- **先有对照物再改代码**：S1 的快照没落盘，S4 的"等价"就无法证明。
- **改名/搬迁必须连注入文本一起改**：本次涉及 vendor 文本里的 skill 名与工具名，门禁 2 兜底。
- **构建产物要校验**：客户端改动必须 pnpm build:client 并确认 verify-client-build.mjs 哨兵通过（历史上构建失败会清空产物）。
- **禁止逐行字符串变换生成代码**：生成器只允许整文件模板拼接（banner + 内容 + footer），不得逐行缩进/替换。
- **失败要响亮**：预算超限、边界不平衡、触达失败一律结构化返回，禁止静默降级为空串。
- **任务闭环**：每卡完成即 reqboard_task_report（做了什么/改了哪些文件/下一步），再 reqboard_task_move(done)——注意 done 之间 60s 间隔门。

## 4. 分工

- P0（t1-t6）体量最大但机械，交由 **background subagent** 按本文 S1-S6 执行；本窗口负责独立验证（不采信自述）与任务卡状态。
- P3（t9-t11）涉及框架不变量，**本窗口或新窗口亲做**，失败即按纪律回 planning。
- 任何一步发现设计不成立 → 停手，回 planning 重提计划，不在实施期私改设计。

## 5. 收尾清单（12 卡全部 done 后）

**已完成**：t1-t12 全部 done，每张均经父窗口独立复核（重跑命令、亲手故障注入、逐条核验自述）；浏览器包泄露已修（293,225 → 209,934 字节）。

**剩余三步**：

1. **部署后核验**（host 侧改动必须重启 profile 才生效）：重启后核验 ①`GET /dashboard/api/reqboard/injection-log?window=<id>&k=20` 返回结构正确 ②`GET /dashboard/api/reqboard/session/:id/progress` 无 500 回归 ③任务卡/需求进度接口正常 ④客户端「本次注入（只读）」块渲染。
2. **提交验收材料**：`reqboard_submit(kind=verification)`，证据含各卡汇报、复核命令与输出、门禁故障注入记录、泄露修复前后 bundle 字节数、两处偏离裁决（P0 三处、t12 探针排除）。
3. **归档材料**：`reqboard_submit(kind=archive)`。

**已知缺口（必须写进验收材料，不掩盖）**：

- **开态（NODE_ISOLATION=on）在真实窗口的替换未实测**：生产 idle 探针依赖 sessionProjections 的 turnBoundary 投影，投影不可得时保守判"不空闲"→ 更可能落 `skipped/agent_busy` 留痕而非真替换。开关**默认关**，故无生产行为变更；开启前需在真实窗口观察一次。
- 按需片段（TDD/SDD/worktrees/dispatching/code-review/横切）仅 vendor 落盘、未注册成分片（注册即需被路由/include 命中，否则违反"无孤岛"门禁）→ 留待"节点内子步骤"设计。
- wiki_probe 基线仍有 2 死链 + 1 孤儿，来自 `docs/INDEX.md`（未改动，HEAD 既有），与本需求无关。

