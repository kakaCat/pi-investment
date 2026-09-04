# L4-B 落地：genome benchmark 静态复核腿 + 验证门结构防御

> 日期：2026-09-03（周四）
> 作者：investor（w-8366e526）
> 类型：L4 元学习 · B1-B4 代码实现（用户已确认范围；B5 Chain-A/B 统一与 meta_* 暂缓）
> commit：`aa1213c4`（feat/l4b-benchmark → main，fast-forward）
> 代码复核基准：先验代码、后落实现——所有结论带文件/行号证据

## 0. 背景（为何做静态腿）

零号基线审计（见 `l4-zero-baseline-genome-g1-g18-20260903.md`）坐实：

- g1→g18 全部为文本段更新，**R-005→R-010 只增不验**
- 38%（7/18）版本是验收/测试噪声；8/25 验证门裁决在空样本上转正
- validation_gate 的 judgeCandidates 只对 **strategy_param 类候选**有回测腿（`strategy_id && mutation_type!=='prompt'`），**prompt/rule 文本变异无任何内容质检**——只能干等记忆样本，且空更新/测试噪声不会被拦截

## 1. 实现内容（B1-B4）

### B1 candidates.ts：健康检查 + git 快照取数（`agent-dh/packages/evolver/src/candidates.ts`）

- `CandidateRecord.health_check` 扩展：`passed / checked_at / issues / size_delta / rule_changes / substantive / note`
- `runHealthCheck()`（纯函数，可单测）四项检查，与 `genome/src/guard.ts` 同口径（guard 在 genome_update 写入时 throw；此处收集为 issues 供复核留痕，**两处规则必须同步改动**）：
  1. `braces`：未知 `{{var}}`（已知变量清单仅 `genome_version`）
  2. `size`：>8000 字符
  3. `dup_rule_id`：rules 段标题定义行重复（`/^#{1,6}\s*(R-\d{3})\b/gm`，正文引用不算）
  4. `empty_update`：与基线去空白后完全相同 → 无实质变更（噪声候选特征）
  - 附带 diff 画像：`size_delta` + `rule_changes.{added,removed}`（P4 元学习归因数据地基）
- **快照取数防漂移**（关键设计）：`getSectionContentAtGenome()` 用 `git show <history[].git_commit>:sections/{s}.md` 取**登记时 genome 版本**的段内容（history 条目 `version===rec.genome_version && section===rec.section` 定位 commit），事后复核不因当前 sections 文件被后续版本覆盖而失真
- `registerCandidate()` 登记时即算并持久化 health_check

### B2 新工具 genome_benchmark（`agent-dh/packages/evolver/src/tools/GenomeBenchmarkTool/`）

命名规避：quantsys-v2 已有 `benchmark_run`（性能 benchmark），故用 `genome_benchmark` 避免同名碰撞。

- 参数：`section?` / `candidate_id?` / `include_promoted?`（默认 false：只看 watching）/ `reject_failed?`（**默认 true，显式兜底**——安全默认值不依赖框架注入）
- 行为：
  - watching 且结构不通过 + reject_failed=true → 置 `rejected`（note 注明"L4-B 结构复核拒绝…建议 genome_rollback 复原"）
  - `health_check` 缺失（L4-B 前登记的旧候选）→ **degraded 标注 `health_passed:null`，绝不假通过**
  - summary 输出筛选范围 + 计数（structure pass/fail / empty_update / rejected / degraded）
- 依赖 BaseTool 模式（validate/execute/wrap + metadata），随 EvolverPlugin 注册自动进 schema smoke

### B3 validation_gate 静态防御 + 摘要（`agent-dh/packages/evolver/src/tools/ValidationGateTool/ValidationGateTool.ts`）

- judgeCandidates：watching 候选若 `health_check 存在且 !passed` → 直接 `rejected`（不浪费回测/观察期），note 注明"（验证门防御，未调用 rollback）"
- 全部 verdict 携带 health 摘要（`health_passed / substantive / health_issues`）
- promoted 时追加警示：health_check 缺失 → "（⚠️ 无结构复核记录：仅经验样本证据）"；substantive=false → "（⚠️ 内容无实质变更/空更新——低价值转正）"，并写入 genome_promote reason
- **语义护栏**：health_check 缺失 ≠ 拒绝（降级走原裁决），只有"存在且失败"才触发防御——不借故误杀存量旧候选

### B4 prompt/render（`GenomeBenchmarkTool/prompt.ts` + `ValidationGateTool/prompt.ts`）

- genome_benchmark output.schema + markdown render（复核计数条 + 逐条画像）
- validation_gate render 每个 verdict 追加健康注解（✅ 通过 / ❌ issues / ⚠️ 无记录或空更新）

## 2. 测试证据（49/49 绿）

```
Test Files  6 passed (6)   Tests  49 passed (49)
```

| 测试文件 | 例数 | 覆盖 |
|---|---|---|
| `packages/evolver/tests/health-check.test.ts`（新增） | 12 | runHealthCheck 纯函数 7 例（braces 未知/已知、size、dup_rule_id、empty_update、无基线降级）；**临时 git 仓库集成 5 例**（getSectionBaseline 按 history git_commit 定位、getSectionContentAtGenome 快照事后不漂移、attachHealthCheck 基于登记快照判空更新、registerCandidate 空更新留痕、越界/null 安全） |
| `packages/evolver/tests/gate-health-defense.test.ts`（新增） | 4 | **真实实例化 ValidationGateTool + 临时 genomeDir** 直调 judgeCandidates：health fail→rejected（不进回测/观察）、health 缺失→降级 extended 不误杀、pass→正常裁决、有样本 promote 携带摘要 |
| evolver 既有 3 文件 | 14 | 基线回归（候选 store / judge 零样本门槛 / searchRewards） |
| `tests/plugin-schema.smoke.test.ts` | 19 | 全插件构造即编译 schema（evolver 含新工具） |

过程修复（诚实记录）：
- schema 铁律违规 2 处 → DSL 报错捕获：array 节点误写 `additionalProperties: true`；`type:['boolean','null']` 联合类型 DSL 不支持 → 改 `oneOf:[{type:'boolean'},{type:'null'}]`
- agent-dh node_modules 破损（09-02 清理后未重装，所有跨包测试跑不了，与本次改动无关）→ `npx pnpm@8.15.0 install`（lockfile v6 匹配）+ worktree packages/*/node_modules 批量 symlink 到主区

## 3. 存量状态与诚实边界

- **live candidates.json 仅 2 条 promoted（g8/g10 lessons，均 2026-08-25 前登记）**，无 watching → genome_benchmark 默认 scope 现返回空、gate 防御等待未来 candidate 触发。这是"能力就绪但无存量输入"的真实状态，非缺陷
- include_promoted=true 可对存量 2 条补画像（health_check 缺失 → degraded 标注）
- **Chain A 空转不在本范围（B5 暂缓）**：agent-dh evolution_* 工具链仍走 Agent OS evolution_handler.go 的占位阶梯（0.05*i）与空 evolution_runs 表；本实现只解决"候选进了验证门之后"的质检，不解决"候选为什么少/链 A 空"
- health_check 是登记时点复核留痕：若候选内容在 genome_update 写入后被手工改坏，事后复核读 git 快照可还原事实（不漂移），但不会重新跑 guard（guard 只管写入路径）

## 4. 下一步（非本次范围）

- 盘后窗口：执行 L4-A 工单隔离动作（含本次已修正的 source-filter 证伪行）
- 9/5-9/6：evolution 定时任务跑起来后，观察 genome_benchmark 对新登记候选的画像与 gate 防御触发情况
- B5（Chain A/B 统一 + leaderboard 占位诚实化）待用户另行确认

## 5. B5 状态更新（2026-09-05，RFC 012 收尾，w-8366e526）

> §3 的「Chain A 空转不在本范围（B5 暂缓）」已被 RFC 012（策略进化引擎，docs/rfcs/012-strategy-evolution-engine.md）在 agent-dh 侧完整解决：

- **A 链统一 + 占位退役**：agent-dh evolution_* 工具已从 Agent OS evolution_handler.go 占位阶梯（0.05×i）切到 qv2 真实回测进化引擎（`e00d4ee4`/`edd663f0`/`bca61114`/`1fa859ca`，均 w-8366e526）；leaderboard 占位诚实化三态（qv2_real/degraded/empty，无任何占位数字），P0-P2 Live 验证通过（见 RFC 012 §10）。
- **B 链 8/14 断点恢复（P3）**：`quantsys-v2/adapters/inbound/fastapi_app/daily_jobs_bootstrap.py` 注册 `evolution_fitness` 盘后任务（20:35 周一~五）调 `EvolutionFitnessService.compute_all_accounts`（双侧捕获，幂等 upsert）——账户行为 fitness 恢复日度续采，与策略参数进化分域。
- 数据链终态：策略参数进化（A 链语义）走 qv2 evolution_strategy_runs 真实回测；账户行为 fitness 走 evolution_fitness 日度续采——两条链真实化且分域清晰，本 work-log §3 悬置的 B5 关闭。
