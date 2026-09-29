# 验收自检清单 · REQ-202609262349-1518（RTM YAML 追溯基础设施）

- 自检时间：2026-09-27 11:30（+0800）
- 执行者：agent（窗口 session-9f2c6c84）
- 台账状态：`accepting` · 14/14 任务 done · 验收单 v2（2 项 pending，无 failed）
- 运行态：PID 42925（11:01:06 启动，cwd=`/Users/yunpeng/pi-investment/agent-dh`），`dist/index.mjs` 于 11:00 重建

> **边界声明（重要）**：运行中的服务 = 本需求**已提交进 main 的改动** **+ 另一窗口尚未提交的在途改动**
> （新增 `MoveTool`/`TaskMoveTool`、`task-transition.ts`、`plan-landing.ts`、`task-completeness.ts` 等 30+ 文件）。
> 下文所有「实测」都是这个混合态下的读数 —— 也就是说，它们证明了**追溯功能在真实服务里跑得通**，
> 但不能单独归因于我提交的那三个 commit。

## 一、节点清单 · 逐条自检

### 1) 交付物：追溯数据真的到了接口（FR-5 追溯关系索引）

命令（四个阶段逐个调用 `stage/<stage>`，取 `data.body`）：

```bash
curl -s http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-202609262349-1518/stage/<stage>
```

| 阶段 | body.traceability | body.coverage | fr_to_design | design_to_tasks | fr_to_tasks | task_to_tests | fr_to_tests |
|---|---|---|---|---|---|---|---|
| design | 有 | 有 | 9 | 40 | 9 | 14 | 9 |
| decomposing | 有 | 有 | 9 | 40 | 9 | 14 | 9 |
| implementing | 有 | 有 | 9 | 40 | 9 | 14 | 9 |
| accepting | 有 | 有 | 9 | 40 | 9 | 14 | 9 |

判定：**通过** —— 三级链 + 两条跨级推导在四个阶段都真实出现在接口载荷里。

### 2) 交付物：覆盖度三读数（FR-6）

| 读数 | rate | total | covered | uncovered | 判定 |
|---|---|---|---|---|---|
| 实施覆盖度（设计章节 → 任务） | 100 | 40 | 40 | — | 真实 ✅ |
| 测试覆盖度（任务 → 测试） | 86 | 14 | 12 | t-9d53f4、t-dbad8b | 真实 ✅（≥80 门禁） |
| **设计覆盖度（FR → 设计）** | 100 | **0** | **0** | — | **虚假绿 ❌ 见 二-1** |

### 3) 交付物：测试怎么跑、跑出什么（验收要能跑）

| 命令 | 结果 |
|---|---|
| `node_modules/.bin/vitest run packages/tools/reqboard/tests/rtm/` | **11 文件 / 94 例全绿，EXIT=0** |
| `npx vitest run tests/traceability-handler.test.ts tests/transition-guard.test.ts` | **2 文件 / 12 例全绿，EXIT=0** |

### 4) 提交验收材料

- `verification` 产物已登记且**已落章**（`confirmedAt` 已写），验收单 **v2** 已生成（2 项待裁决）。
- 本轮**不重复提交**：重交只会把验收单推到 v3、不改变任何裁决，还会重置当前 pending 项。
  按「同一产物不重复弹框」处置，此处显式跳过而非静默跳过。

### 5) 请人审核

- `reqboard_accept_sheet` 已弹过一次（v2 两项），窗口内未收到作答 → **未记录任何裁决**。
- 按「弹框超时/中断不自动重弹」，本节点停在人工门，等待人工通道（看板验收面板等效）。

## 二、自检中发现的问题（如实报出，不静默降级）

### 二-1【真缺陷 · 直接影响 FR-6 / FR-7】设计覆盖度是虚假绿：分母为 0 却报 100%

现象（design 阶段覆盖度原样输出）：

```json
{"total":0,"covered":0,"uncovered":[],"rate":100,"total_frs":0,"covered_frs":0}
```

根因（三步实证，可复核）：

1. FR 列表来源 `effectiveFRs()` 先读 `rtm-brainstorming.yml` 的 `outputs.requirements` —— 本需求该字段是 **`[]`**（空）。
2. 于是退回实时解析：`parseRequirementFRs(requirement.md)`，其 `FR_LINE` 为
   `/^(?:\*\*|\s*#{2,6}\s*)\s*FR-(\d+)\s*[:：]\s*(.+?)\s*\**\s*$/` —— **要求行首是 `**` 或 `##`**。
3. 而 `requirement.md` 的 FR 标题实际写作 `- **FR-1: RTM 文件结构设计**`（**bullet 开头**）→ 实测输出
   `matched FR lines: 0`。

⇒ `frs = []` ⇒ `calculateDesignCoverage` 分母为 0 ⇒ `rateOf()` 按 vacuous truth 返回 100。

**影响**：FR-7 的「设计 100%」门禁在数值上必然通过（分母恒 0）——**实际从未起拦截作用**；
同时看板覆盖度卡片会给审查人一个误导性的满分。

**注意一个容易看错的点**：`fr_to_design` 仍有 9 个键。它是由设计文档的 `serves:` 标注构建的，
与 `frs` 无关 —— 所以是「**映射是对的、读数却是空的**」，不是数据没生成。

**建议修法（二选一，需人裁决）**：
- (a) 发布期修：让 `FR_LINE` 兼容 bullet 形式 `- **FR-N: …**`，或在 brainstorming 触发点把 FR 写进 `rtm-brainstorming.yml`；修完重跑触发点。
- (b) 验收期记账：本项判「需修改」，由系统生成返工卡再修。

### 二-2【一致性缺陷 · 台账与磁盘不一致】4 个已登记产物在盘上不存在

`reviews/phase1-review.md`、`tests/acceptance-criteria.md`、`tests/test-execution.md`、`tests/unit-tests.md`
—— 四个都是「台账 `registered=True`、磁盘 `on-disk=False`」。它们已被当过期文档删除，但**登记没撤**。
后果：本节点的「上游必读」清单会指挥下一个窗口去读 4 个不存在的文件。

## 三、feature 类型档四项核验

| 项 | 怎么验的 | 结果 |
|---|---|---|
| **接口**核验 | 4 个 stage 接口逐个调用；错误语义：不存在的需求返回 HTTP 404 `{"success":false,"error":"需求不存在","code":"not_found"}` | ✅ |
| **数据契约**核验 | `TraceabilityProjection` 与三段覆盖度投影定义在 `shared/protocol.ts`，全部字段**可选**；`rate` 为 0–100 整数（实测 86、100），非 0–1 小数 | ✅（二-1 的分母问题属读数语义，非字段契约） |
| **迁移与兼容** | 台账 `schemaVersion` 保持 **8**（v9 路线未采纳，无迁移脚本、无回填）；旧字段透传；`deps.cwd` 恒 undefined → 回落 `process.cwd()`（实测 = agent-dh，RTM 可读） | ✅ |
| **验收要能跑** | 见 §一.1 与 §一.3 的命令与输出摘要 | ✅（§二 两项除外） |

## 四、结论（供人工裁决，不代判）

- 主体交付**可复核**：追溯链与覆盖度确实到达了接口；测试可跑且全绿；降级与错误语义正确。
- **但设计覆盖度的 100% 是空转的**，`FR-7 设计门禁` 未真正生效 —— 这一条我不建议按现状放行。
- 建议：`v2-1` 判「需修改」（或先修二-1 再重提）；`v2-4`（缺一条可观察终态的 E2E 用例）同判；
  二-2 可顺手清理登记，避免后续窗口被指引去读不存在的文件。

---

（本清单全部数字均为本轮实测，命令与输出摘要见上；未使用「应该没问题」类表述。）
