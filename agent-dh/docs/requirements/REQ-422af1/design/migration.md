# REQ-422af1 技术设计 · 迁移与分期

> 阶段：planning · 窗口 w-41e7e4cd · 配套：architecture.md

## 1. 迁移目标

从"每阶段一份常量提示词（STAGE_PROMPTS）"迁到"分片库 + 路由解析"，并**保证 P0 逐字等价**（INV-7）——这是本需求唯一的硬性等价要求，也是分阶段推进的安全绳。

## 2. P0 零行为变更的证明方式（先立证据，再动代码）

    第 1 步（改代码之前）：冻结现状快照
      - 写脚本 dump 当前 6 个 stage 的注入文本（逐字、含空白）→ tests/fixtures/stage-prompts-baseline.json
      - 该快照随 P0 一起提交，成为 T21 的对照物

    第 2 步：搭分片库与路由，把现文本按 (stage, 星, 星) 落位
      - 生成器 inline-prompt-fragments.mjs → generated/fragments.ts
      - 解析入口 resolveStagePrompt()，注入点改为调用它

    第 3 步：等价性核验
      - 跑 T21/T22：快照比对逐字一致 + 既有 stage-prompts 测试不改且全绿
      - 跑 tsc（0 错误）+ 既有四条门禁（绿）
      - 任一不一致 → 回滚到快照，不进入 P1

**为什么必须先冻结快照**：没有快照，"等价"只能靠肉眼，而提示词里的空白/标点差异不会被既有测试全部覆盖（本仓已吃过"注入文本里工具名过期"的亏）。

## 3. 分期与开关

| 期 | 内容 | 开关/回滚 |
|----|------|----------|
| P0 | 路由骨架 + 分片落位 + 6 条新门禁 + 快照等价 | 开关：环境变量或配置项 `PROMPT_ROUTER=off` 时回旧常量路径（保留一版即可，验证通过后删除） |
| P1 | brainstorming light/heavy + 类型档 | 分片级回滚：删分化分片即回到兜底档 |
| P2 | planning / implementing / accepting 分化 | 同上，逐节点回滚 |
| P3 | 节点边界同窗口 surface 替换 + 留痕 + 可视化提议 | 开关 `NODE_ISOLATION=off` 默认关；关闭时行为完全等同现状 |

**默认全部保守**：P3 的隔离默认关，先跑通 P0-P2 的取词与门禁，再逐需求开隔离。

## 4. 数据与兼容

- 台账 schema **不变**（v5），无迁移脚本。
- 新增 `prompt-injection-log.json`（state 目录，ring buffer），缺失即视为空；删除该文件不影响功能。
- generated/fragments.ts 不入版本库口径与 dist 同源：由脚本生成，改 md 必须重跑生成（门禁 6 兜底）。

## 5. 风险与回滚点

| 风险 | 触发信号 | 回滚动作 |
|------|---------|---------|
| P0 不等价 | T21 出现任何 diff | 保留快照、回退注入点改动（旧常量路径仍在） |
| 注入变长 | 留痕里 charCount 超 P0 实测上限 | 收紧预算（先量后收），不动分片内容 |
| surface 替换违反不变量 | 替换被拒（不平衡/活动轮次）日志增多 | 关 `NODE_ISOLATION`，退回"只重注入" |
| 人可见效果不符预期（历史消失） | 人反馈"看不到之前的内容了" | 关隔离；或改为替换时保留一条"上一节点结论指针" |

## 6. 交付物清单（本阶段后续由 decomposing 定任务）

    src/domain/prompt/{index,router,budget,types}.ts
    src/domain/prompt/fragments/**            （md 源）
    src/domain/prompt/generated/fragments.ts  （生成物）
    scripts/inline-prompt-fragments.mjs
    scripts/check-prompt-fragments.mjs
    tests/prompt-router.test.ts / prompt-gates.test.ts / prompt-baseline.test.ts
    tests/fixtures/stage-prompts-baseline.json
    docs/architecture/workflow-stages.md      （文档同步：注入路由一节）
