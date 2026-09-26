---
requirement_id: REQ-260926140539-457b
kind: review
title: RTM YAML 追溯基础设施 · 自评审报告
version: 1.0
---

# 自评审报告 · REQ-260926140539-457b

## 结论
20 张任务卡逐卡自检通过，交付可用；**但存在一处必须由人裁决的部署缺口**（见 §4），
故本报告不代替人工验收。

## 1. 逐卡自检（20/20）

| 任务 | 判据 | 证据 |
| --- | --- | --- |
| t-8c8edc 类型定义 | `tsc -p tsconfig.json` exit 0，类型齐备 | 包级编译门禁 |
| t-e57e00 文件 IO | 8 条单测（原子写/版本递增/坏 YAML 不崩） | tests/rtm/file-io.test.ts |
| t-25c956 标注解析 | 12 条单测（含围栏示例不误判） | tests/rtm/parser.test.ts |
| t-3ca532 四级追溯 | 映射与链路断言 | tests/rtm/traceability-coverage.test.ts |
| t-0bf4ae 覆盖度+门禁 | 67%/100%/40% 与阈值点名 | 同上 |
| t-93f4da~t-20151a 六个生成器 | 各节点字段/覆盖度/版本号断言 | tests/rtm/generators.test.ts |
| t-152423~t-eb31cc 五个触发点 | 触发点→文件集合断言 + 失败不阻断 | tests/rtm/triggers.test.ts |
| t-cf2b22/t-66d23c StageOverview | 读取/缺失/装配/降级 | tests/rtm/stage-overview.test.ts |
| t-37e870 端到端 | 7 触发点全流程 + 链路 + 体积 + <5ms | tests/e2e/rtm-yaml-full-flow.test.ts |
| t-c010b8 文档 | 7 触发点表 + 4 段示例 + 压缩规则 | docs/guides/rtm-usage.md |

## 2. 设计一致性
- 数据契约与 `design/rtm-schema.md` / `design/data-model.md` 对齐；`Coverage` 同时给出
  通用四元组（total/covered/uncovered/rate）与 data-model 的领域名（total_frs 等），
  避免两份设计口径打架时被迫二选一。
- 接口与 `design/interfaces.md` 对齐：`RTMGenerator` 提供七个节点方法 + `updateTaskStatus`；
  真正批量更新走 `runRTMTrigger`（触发点门面）。
- 门禁阈值单点在 `rtm/validator.ts`（design/decomposing 100%、accepting ≥80%）。

## 3. 回归与边界
- 生成引擎全部走文件 IO + 只读端口，不 import dsh-pmboard，可脱离运行实例单测。
- dsh-pmboard 九个接线点均为**加性**改动，且 `syncRTMYaml` 内部 try/catch——
  RTM 失败只记 warning，不改变创建/提交/确认/推进的既有行为（FR-9）。
- 全量回归失败集合改动前后逐一致（详见 tests/test-evidence.md 末节）。

## 4. 已知缺口（响亮报出，请人工裁决）
1. **未部署**：dsh-pmboard 源码已接线，但没有重建/重启 `:13080`，因此线上需求
   （含本需求）**尚未自动生成 rtm-*.yml**。生效入口：`python3 agent-dh/scripts/relink-profile.py`
   + `agent-dh/scripts/restart-with-build.sh`。未做这一步的原因是它会在本会话运行期间
   重启服务（会话即跑在 `:13080`），风险高于收益，需人来决定时机。
2. **本构建既有的链路缺失**（非本次引入，见 docs/requirements/.../notes.md）：
   `reqboard_task_move` 工具与「批准计划→自动拆分」链路不可用（`deps.jobs` 未装配），
   故 20 张卡的状态经看板 HTTP 通道推进、完工证据落在任务卡文档；
   任务级 done 凭证门在当前构建中已随工具一并移除。
3. **存量回归欠债**：dsh-pmboard 全量套件 41 个文件 / 197 条失败为仓库既有状态
   （测试辅助引用已删除的工具等），本次改动零新增，但会掩盖新问题——建议单独立项修复。
4. `scripts/docs_index.py --check` 仍报过期：该生成器自身非幂等（每次运行都会改写
   `updated` 字段），改动前的 HEAD 状态同样 --check 失败；不在本次范围。

## 5. 验证方式（可复核）
```bash
cd agent-dh
npx vitest run packages/tools/reqboard/tests      # 13 files / 95 tests passed
cd packages/tools/reqboard && npx tsc -p tsconfig.json   # exit 0
npx vitest run packages/web/dsh-pmboard/tests     # 41 failed / 197 failed，与改动前逐一致
```

---

# 补评审（v1.1 · 2026-09-26）：把 requirement.md 要的、首轮卡表漏掉的部分补上

## 6. 首轮交付的缺口（人提出质疑后复核确认）

首轮 20 张卡按卡验收标准全部达标，但**卡表本身漏了 requirement.md 明确要求的能力**，
按「需求文档才是甲方」的口径，这是交付缺口，不是可选项：

| 需求文档要求 | 落点 | 首轮状态 | v1.1 状态 |
| --- | --- | --- | --- |
| FR-2/FR-5 覆盖度硬门禁（设计<100% 拒提交、实施<100% 拒批准、测试<80% 拒验收） | requirement.md L262-281 / L375-393 / L827-846 | ❌ 校验器写好了但**零调用** | ✅ 三个触发点接线 |
| FR-8 节点输入包装配 + 压缩模式 | requirement.md L1442-1523 / design/interfaces.md §3.1 | ❌ `assembleNodeInput` 全仓 0 处 | ✅ 新增 `dive/node-input.ts` + 注入输入包 |
| FR-8 Dive 决策（能不能推进/下一站/卡在哪） | design/interfaces.md §3.2 | ❌ `makeDiveDecision` 不存在 | ✅ 新增 `dive/decision.ts` |
| FR-4 Level 3 测试覆盖度（读测试文档的 covers:） | requirement.md L1240-1247 | ⚠️ 口径错位：不扫 `tests/` → 真实需求恒 0% | ✅ 修复发现口径（真实读数 0% → 95%） |

## 7. v1.1 做了什么（逐项 + 证据）

1. **`packages/tools/reqboard/src/dive/node-input.ts`**（新）：`assembleNodeInput(workspaceRoot, stage, reqId, 'full'|'compressed')`
   + `assembleCompressed` + `generateNextAction` + `estimateTokens`。压缩规则按 FR-8：
   状态→`2/5 done, 2 in_progress`、任务→只留进行中 `id@phase`、覆盖度→只留 rate/uncovered。
2. **`packages/tools/reqboard/src/dive/decision.ts`**（新）：`makeDiveDecision` 按节点给出
   `{can_proceed, next_stage, reason, coverage, blockers}`，阈值单点复用 `rtm/validator.ts`。
3. **注入**：`node-input-package.ts` 新增可选 `rtm` 块与渲染节；`IsolateNodeContext` 读盘后注入
   （无 RTM 数据 → 不追加，旧输出逐字节不变）。
4. **门禁接线**：`rtm-yaml.ts` 新增 `coverageGateOf(stage, triggerResult)`；
   `RTMTriggerResult` 增加 `coverage` 字段（触发点生成完把覆盖度带回给调用方）。
   `SubmitDesignArtifacts`（design 100%）、`ConfirmArtifact(target=plan)`（实施 100%）、
   `SubmitVerification`（测试 ≥80%）三处接硬门禁，**存量/直种需求沿用本仓 isLegacy 口径豁免**；
   RTM 数据缺失/生成失败一律不拦截（FR-9）。
5. **测试发现口径修复**：`RTMContext.testFiles` 增扫 `tests/*.md`（本仓测试证据的落点），
   否则测试覆盖度恒为 0——门禁会把真需求全拦下（这正是先修它再接门禁的原因）。
6. **测试**：新增 `tests/rtm/dive-integration.test.ts`（12 条），reqboard 套件 12→13 文件、83→95 条全绿；
   dsh-pmboard 全量回归失败集合**逐一致（41/197）**，包级 `tsc` 错误数 149 不变（零新增）。

## 8. 仍未做（响亮报出，请人工裁决）

1. **FR-11（Agent Teams 并行执行）未落地**：本构建的 `reqboard_task_run` 依赖 `deps.jobs`
   （`AdvanceTool` → `DSH_JOBS_UNAVAILABLE`），本仓既有的自动实施链不可用；
   20 张卡首轮也是经看板通道推进的。要真做需要先修宿主 `ctx.jobs` 装配——属另一条线。
2. **Dive 自动化闭环未接**：`makeDiveDecision` 已是可调用的纯函数，但
   `ReqboardDiveManager.getActiveRequirement()` 仍是 `return null` 的桩（L110-115），
   所以「Dive 逐节点自动决策 → 推进/回退」还没跑起来；把它接上需要实现需求查询端口。
3. **实施门禁在"先批准后落库"的流程里是空转**：`confirm:plan` 预检时台账还没有任务
   （本构建拆分落库后于批准），`total=0` → 不拦截。要真正执法需先改"计划任务先落库"的数据流。
4. **未部署**：同 v1.0 §4.1——源码已接线，但 :13080 未 rebuild/restart，线上需求
   （含本需求）尚未自动生成 `rtm-*.yml`。
