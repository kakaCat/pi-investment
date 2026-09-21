---
req_id: REQ-4842fe
doc: design/test-cases
serves: FR-1, FR-1b, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-14, FR-15, FR-16
status: design
---

# REQ-4842fe 设计 · 测试用例

> 口径：每条用例给"跑什么 / 看到什么算过"。**禁止 grep 式断言代替契约断言**（现有 `tests/reqboard-task-execute.test.ts:67` 只断言字符串包含 `ctx.subagent` —— 这正是被本需求修正的反面教材）。

## 1. 映射表与逃生舱口  `serves: FR-1, FR-1b`

| # | 场景 | 期望 |
|---|---|---|
| 1.1 | 各类型父卡展开 | feature/refactor=dev,integrate,review,test；bug=repro,fix,review,regress；doc/chore=dev,review；spike=probe,review；research=collect,analyze,review；data=prepare,run,verify,review；ops=change,dryrun,apply,verify,review；review-only=review |
| 1.2 | 未映射类型 | 回退 `dev,review` 两卡，且展开不报错 |
| 1.3 | 显式 stages 覆盖 | 计划声明 `stages:[collect,analyze,review]` → 实际落库子卡顺序与声明一致 |
| 1.4 | 非法 stages | 含自由文本 / 空数组 / 重复项 → 拒绝建卡，错误码明确 |

**跑法**：`pnpm vitest run`（新增 `SubtaskTemplate.spec.ts`）纯函数用例。

## 2. 数据契约与状态机  `serves: FR-2, FR-5, FR-14, FR-15`

| # | 场景 | 期望 |
|---|---|---|
| 2.1 | 旧台账读取 | 无 parentId/stageKind/attempt/revisions/autoRun 的台账可读、看板可渲染，行为不变 |
| 2.2 | 子卡转移收紧 | 子卡 `in_progress → integrating` 被拒（invalid_transition / human_gate 之外的明确错误） |
| 2.3 | 子卡失败回退 | `in_progress → todo` 成功且 `attempt` +1、写 `revisions`（kind=rollback） |
| 2.4 | done 卡重开 | 人工 `done → in_progress` 成功并写 `revisions`（kind=reopen）；agent 身份调用被拒（human_gate） |
| 2.5 | 需求回退上游 | `implementing → design` 仅人工可通过；agent 调用返回 REQBOARD_HUMAN_GATE |
| 2.6 | 幂等展开 | 同一父卡重复触发懒展开 → 子卡数量不变（INV-3） |
| 2.7 | 悬空子卡 | 手工构造 parentId 指向不存在卡 → 读取/校验报 INV-1 违规 |

## 3. 叶子执行与凭证  `serves: FR-4, FR-6`

| # | 场景 | 期望 |
|---|---|---|
| 3.1 | 脚本契约门禁 | 生成脚本静态扫描**只含** `agent/parallel/pipeline/phase/log`；出现 `ctx.`、`subagent`、工具名 → 生成阶段即失败 |
| 3.2 | 真跑一次 run（冒烟） | 用一个最简单的脚本（`return {ok:true}`）经 `ctx.workflowEngine.start` 跑通，`stopReason=completed`，随后 `dispose()` 不悬挂 |
| 3.3 | 引擎不可用降级 | 强制令引擎缺失 → 子卡标记失败并暂停（不静默成功） |
| 3.4 | 子卡凭证三项 | 缺 report / 文件 mtime 早于开工 / stopReason 非 completed → 任一不过即子卡不 done |
| 3.5 | 父卡凭证 | 存在未 done 子卡时父卡不得 done（INV-5） |
| 3.6 | pages 构建新鲜度 | 子卡改了 `packages/pages/*/src/**` 而 `lib/client.js` 未更新 → 子卡凭证不过 |

## 4. 自动链（事件链）  `serves: FR-11, FR-12`

| # | 场景 | 期望 |
|---|---|---|
| 4.1 | 全自动到验收（主用例） | 建测试需求 → 批准计划（模拟人工确认）→ **不再调用任何人工工具** → 断言最终需求 `accepting`，全部父卡/子卡 done |
| 4.2 | 零点击校验 | 4.1 全程不出现"确认拆分清单"弹框（门已合并），不要求看板点击 |
| 4.3 | 幂等重放 | 对同一需求重复触发同一事件 → `outcome=noop`，台账 revision 不变 |
| 4.4 | 单飞锁 | 并发触发同需求两个事件 → 一个执行、另一个被拒或 noop（无双重执行） |
| 4.5 | 停滞熔断 | 构造连续 noop 达阈值 → `autoRun=false` + 告警 + PAUSE |
| 4.6 | 崩溃恢复 | 中途杀掉执行器（模拟重启）→ 重新扫描后从"下一个事件"续跑，最终完成 |
| 4.7 | 暂停/继续 | 置 autoRun=false 后不再有新事件；置回 true 并触发一次 → 续跑 |

## 5. 失败、暂停与返工  `serves: FR-13, FR-14, FR-15`

| # | 场景 | 期望 |
|---|---|---|
| 5.1 | 子代理返回 null | 子卡失败退回 + attempt+1 + 失败评论；需求 autoRun=false；高优告警发出；**不执行后续卡** |
| 5.2 | 不自动重试 | 失败后无任何自动重跑（事件计数不变） |
| 5.3 | 处置弹框 | 暂停时弹出三选（重跑 / 退回上游 / 取消）；选"重跑"→ 链恢复；选"退回上游"→ 需求回 design |
| 5.4 | 退上游后就地更新 | 重新批准计划后：**卡数不变**、受影响父卡字段被更新、每张被改卡新增 `revisions`（kind=update） |
| 5.5 | 回滚留痕 | 子卡失败回退、done 卡重开 → 均写 `revisions`（rollback / reopen），字段与原因齐全 |
| 5.6 | 自动链不重开 done 卡 | 自动事件扫描不产生任何 `done→in_progress` 转移 |

## 6. 并发与冲突  `serves: FR-9, FR-10`

| # | 场景 | 期望 |
|---|---|---|
| 6.1 | 并发上限 | 同需求第 4 张父卡开工被拒（上限 3） |
| 6.2 | 父卡层并行 | 两张互不依赖父卡的子卡链同时推进、互不阻塞；都完成后 rollup 正常 |
| 6.3 | 子卡依赖不跨父卡 | 子卡 dependsOn 只指向同父卡内前序卡；构造跨父卡依赖被拒 |
| 6.4 | 拆分期冲突拦截 | 两张互无依赖父卡 implementation 声明同一文件 → decompose 拒绝 |
| 6.5 | 运行期覆盖兜底 | 构造某文件 mtime 落在另一在跑父卡的子卡窗口内 → 该子卡判失败并暂停 |

## 7. 交互面  `serves: FR-16`

| # | 场景 | 期望 |
|---|---|---|
| 7.1 | 批准计划弹框文案 | 文案含"批准后自动拆分并立即开跑"与干预方式说明 |
| 7.2 | 节点推进不弹框 | 4.1 全程除批准计划与验收外无其他弹框 |
| 7.3 | 看板定位 | 关闭 autoRun 后看板可观察进度；不操作看板不影响链的暂停语义 |

## 8. 门禁与回归  `serves: FR-4`

| # | 场景 | 期望 |
|---|---|---|
| 8.1 | 工具 schema 冒烟 | 新增工具进入 `tests/plugin-schema.smoke.test.ts` 的 PLUGINS，构造全部 schema 通过 |
| 8.2 | 旧用例回归 | `pnpm vitest run`（dsh-pmboard 全部既有用例）不退化 |
| 8.3 | 台账兼容回归 | 用真实存量台账副本跑读取 + 渲染，无异常 |
| 8.4 | 层边界门禁 | domain 不 import 运行时 `@deepseek-ai/*`；`ctx.workflowEngine` 只出现在 adapter |

## 9. 反向用例（防"看起来在工作"）  `serves: FR-4, FR-11`

| # | 反例 | 期望 |
|---|---|---|
| 9.1 | 把 `ctx.tools.workflow` 当可用工具 | 用例显式断言实现里不出现该调用（本 profile 已被禁） |
| 9.2 | 只断言脚本字符串 | 用例必须断言 hook 白名单全集，字符串包含式断言不合格 |
| 9.3 | 让 run 内改状态 | 用例断言状态变更发生在宿主侧（脚本返回值可复现） |
