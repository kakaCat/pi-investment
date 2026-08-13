# 全局执行顺序与并行图（召回重设计 + 三 Agent 拆分）

- 日期：2026-08-13
- 适用计划：`2026-08-13-memory-recall-redesign.md`、`2026-08-13-agent-domain-split.md`
- **并行约束：委派任务只用一个执行模型**（同一模型的多个并行会话）；k3 独立一条泳道，负责 H 级任务与全部验收合并。

## 泳道图

```mermaid
flowchart TB
  subgraph K3["泳道 1：k3（Claude）—— H 级任务 + 全部验收合并"]
    direction TB
    K1["P0-T2 floor 分布测量定值<br/>⬜ 随时可开始"]
    K2["P1-T2 RecallService 编排+端口<br/>⬜ 等 P1-T1 合并"]
    K3a["A0-T3 会话工厂装配（总闸门）<br/>⬜ 等 A0-T1+A0-T2 合并"]
    K4["P2-T1 SDK 扩展接线 → P2-T2 删 wrapper → P2-T3 全通道验收<br/>⬜ 等 P1-T1~T3 合并"]
    K5["A2-T2 weekly_evolution 迁移<br/>⬜ 等 A2-T1 合并"]
    K1 --> K2 --> K3a --> K4
    K3a --> K5
  end

  subgraph EXE["泳道 2：执行模型（同一模型，可开多个并行会话）"]
    direction TB
    E1["P0-T1 v2 质量门<br/>⬜ Wave 1"]
    E2["P1-T1 领域层四文件<br/>⬜ Wave 1"]
    E3["P1-T4 v2 审计 API+PG 表<br/>⬜ Wave 1"]
    E4["P1-T5 前端审计页<br/>⬜ Wave 1（验收等 P1-T4 部署）"]
    E5["A0-T1 工具分组<br/>⬜ Wave 1"]
    E6["A0-T2 RoleProfile<br/>⬜ Wave 1"]
    E7["P0-T3 env 接线+重启验证<br/>⬜ Wave 2：等 P0-T1 合并 + P0-T2 出值"]
    E8["P1-T3 审计适配器<br/>⬜ Wave 3：等 P1-T2"]
    E9["A1-T1 recall_audit 工具+记忆Agent<br/>⬜ Wave 3：等 P1-T4 + A0-T3"]
    E10["A2-T1 进化提示词+skill工具<br/>⬜ Wave 3：等 A0-T3（文案 k3 审）"]
    E11["A1-T2 每日审计任务<br/>⬜ Wave 4：等 A1-T1（文案 k3 审）"]
    E12["A3-T1 渠道微调<br/>⬜ Wave 3：等 A0-T3"]
  end

  E2 -->|合并后| K2
  E5 -->|合并后| K3a
  E6 -->|合并后| K3a
  E1 --> E7
  K1 -->|floor 终值| E7
  K2 --> E8
  E3 --> E9
  K3a --> E9
  K3a --> E10
  K3a --> E12
  E9 --> E11
  E10 --> K5
```

## 波次表（按时间推进）

| 波次 | k3 泳道 | 执行模型泳道（同一模型，并行会话数按你的带宽定） |
|---|---|---|
| **Wave 1**（全部无依赖，立即开工） | P0-T2 floor 测量 | P0-T1 ／ P1-T1 ／ P1-T4 ／ P1-T5 ／ A0-T1 ／ A0-T2（6 个任务文件全不相交） |
| **Wave 2**（Wave 1 陆续验收合并后） | 验收合并 → 做 P1-T2、A0-T3 | P0-T3（等 P0-T1+floor 值） |
| **Wave 3** | 验收合并 | P1-T3 ／ A1-T1 ／ A2-T1 ／ A3-T1 |
| **Wave 4** | P2-T1→T2→T3 接线与全通道验收；A2-T2 进化迁移 | A1-T2 每日审计任务 |
| **Wave 5** | P3/A4 观察期：注入率与分账统计一周 → floor 调优定稿 | — |

## 关键路径与建议

1. **总闸门是 A0-T3（k3）**：拆分计划所有后续任务都等它；A0-T1/A0-T2 回来后优先验收合并这两个。
2. **最快可见收益**：P0 线（质量门）——P0-T1 合并 + P0-T2 出值 + P0-T3 重启，噪音召回立刻消失，不依赖任何其他任务。
3. **并行安全约定**（防文件冲突）：
   - P0-T1 独占 `domain/memory/service.py`；P1-T4 禁碰 `service.py`/`hybrid_search.py`；
   - A0-T1 独占 `tools/index.ts` 与 `groups.ts`；A1-T1/A2-T1 因需改这两个文件，被排在 A0-T3 之后；
   - 每个任务独立 worktree，合并统一由 k3 走 merge-back 流程。
4. **每个执行模型任务完成后**：任务标题状态 ⬜→👀，k3 验收通过改 ✅ 并合并；打回改 ❌ 附原因，同一模型会话内返工。
