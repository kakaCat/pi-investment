# 架构设计（REQ-260927100007-b8ba）

> 本文件回答"改哪里、为什么这么改"。分两层：**需求级**（落章/推进/守卫）与**任务级**（收敛点/工具）。
> 每个二级/三级标题都带 `serves: FR-x`，对应 `requirement.md` 的条款。

## 1. 共同根因与总原则 <!-- serves: FR-1,FR-2,FR-3,FR-8,FR-13 -->

**根因**：把"该发生的事"排到了"人点头"之后，并委托给一个可能不存在的执行者；
且每个状态机缺少**唯一且会自校验的收敛点**。

**总原则（三条，贯穿全部 FR）**：

1. **原子**：落章 = 落章 + 必要落库 + 推进，同一调用内完成；任一步失败则整体停下并响亮留痕（FR-1/FR-2/FR-13）。
2. **单一收敛点**：状态只能经 `transitionRequirement`（已有）/ `transitionTask`（本需求补）改变；
   业务路径不得直接赋值（FR-8）。
3. **跨状态机完整性**：阶段推进必须校验下游状态机的完整性（FR-3）。

## 2. 需求级：落章与推进必须原子 <!-- serves: FR-1,FR-2,FR-13 -->

- **批准计划**（`confirm-settle` 批准块）：落章 → **同步落库任务卡** → `decomposing → implementing` + `autoRun=true`。
  落库失败 → 不推进，写 `advance.pausedReason` + 系统评论 + 告警。
- **文字证据路径**（`ConfirmArtifact`）：落章后**必须接着推进**（复用 `confirm-settle` 的推进块：
  `advanceTargetFor` + 人工门 `transitionRequirement`），不得只落章后指向一个不存在的工具。
- 失败一律**响亮**：不推进时必须留下"原因 + 可执行命令"，不得沉默（当前实测是沉默，见 FR-13）。

## 3. 需求级：阶段推进的任务完整性守卫 <!-- serves: FR-3 -->

- 新增 application 层纯判定 `taskCompletenessGap(req, tasks)`：目标态 `implementing`、
  非 legacy、`plan.tasks.length > 0` 且该需求 **0 个未取消任务** → 返回缺口文案。
- 调用点：`confirm-settle` 的推进前 + `MoveRequirement` 路由（看板移动）**共用同一判定**。
- **只拦确定异常**（"计划有卡却一张没落库"）；`plan.tasks.length === 0` 的空计划不拦（迁移/回填/纯文档需求）。

## 4. 任务级收敛点 transitionTask <!-- serves: FR-8 -->

- 新模块 `application/internal/task-transition.ts`，与 `token-usage.transitionRequirement` 对称：
  内部调 `assertTaskTransition(from, to, actor.kind, role)` → 改 `status/version/updatedAt/updatedBy` →
  `recordStatus` 追加状态事件；`allowIllegalTransition` 逃生舱仅供迁移/回填。
- **四处写入点改为经它流转**：`ExecuteTask`、`AdvanceChain`、`failure-handling`、`http/routers/tasks`。
- 执行段副作用（`claimedAt/claimedBy`、`executions` 开闭）保持在调用方；收敛点只管**状态语义**。

## 5. Dive 两半与投递白名单 <!-- serves: FR-11 -->

- 契约（`docs/architecture/reqboard-dive-mode.md`）：驱动点 = 整 agent 空闲；只有 `armed + active` 才起轮；
  事件不直接投递；回合消息带 `source.kind='dive'` 且走预留→投递→准入。
- **采集半只采集/簿记/记录，不投递**：删除阶段纪律投递（纪律已在每次 system prompt）；
  里程碑催办改为"登记 + `requestDrive`"，由 round 半在 armed+active 时投递；非 armed 只写 comment。
- **投递白名单**：`deliver()` 只保留"人点头后的收尾/交接/唤醒"（pending-confirm `wake`、闸门链 H4、失败告警）。

## 6. RTM 触发点与刷新集合 <!-- serves: FR-6,FR-12 -->

- `task:status` / `task:report` 的刷新集合补 `rtm-decomposing.yml`（实施覆盖度随任务变化）。
- 窗口绑定投影：新增 `bind` 触发点，绑定发生时刷新 `rtm-lifecycle.yml`；
  并让**读取方存在**（Dive 投递目标优先读 RTM，或如实声明无消费者）。
- RTM 永远失败不打断主流程（既有 FR-9 契约），但**主流程自身的失败必须响亮**。

## 7. 终态与响亮化 <!-- serves: FR-2,FR-9,FR-13 -->

- 确认门挂起（`pending=true`）期间：同窗口写路径工具代码级拒绝（`REQBOARD_CONFIRM_PENDING`），
  `reqboard_status` / `reqboard_confirm_receipt` 保持可用。
- `reqboard_status` 返回体必须 lossless（递归无 `undefined` 属性），否则绑定窗口必然失败。

## 8. Dive 在人工门主动弹框 <!-- serves: FR-14 -->

**要解决的矛盾**：Dive 的里程碑提醒说「**立即**调 reqboard_ask_confirm」，而铁律说
「弹框超时/中断**不自动重弹**」——两条规则互撞，结果是**没有任何一方保证人会看到框**
（实测：提醒 3 次，人一次都没看到框）。

**设计**：把兜底从"提醒 agent"改为"**保证弹框**"：

- Dive 在 idle 跑批时计算**门状态**（`gateFromStage(status)`）：
  门产物未确认 → 弹「确认产物」；门已满足但状态未推进 → 弹「推进确认」。
- 弹框走**受信内部入口**（只对 Dive 开放；idle 期无法通过工具层的 live-driver 认证）。
- **有边界重弹**：同一次等待内只弹一次（不刷屏）；跨回合可再弹，冷却 ≥5 分钟、上限 2 次，到顶留痕停手。
- **保留不变量**：五道人工门仍只能由人发起（肯定项 `actor=human`）；Dive 只请人点头。

**与既有规则的关系**：本条对「弹框超时/中断不自动重弹」做**受控放宽**（跨回合可重弹 + 冷却/上限），
理由是原规则与 Dive 提醒互相抵消；放宽范围写进验收（TC-15），不涉及人工门本身的强度。
