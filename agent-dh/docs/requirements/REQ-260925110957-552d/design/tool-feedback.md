---
requirement_refs: [FR-10]
---

# 工具反馈设计（REQ-260925110957-552d · FR-10 扩展）

> 所有 pmboard 工具的 description / render / 错误文案优化规范。

## 设计原则 <!-- serves: FR-10 -->

### 1. description 三要素 <!-- serves: FR-10 -->

**格式**：`[职责]. [适用场景]. [注意事项].`

**示例**（优化前 vs 优化后）：

❌ **优化前**：
```
推进本窗口已绑定需求的状态
```

✅ **优化后**：
```
推进需求状态（项目看板泳道）。里程碑处自行推进（方案定→decomposing，开工→implementing，交付→accepting）；取消/归档需人工操作。写清 reason（供复盘）。
```

### 2. render 统一格式 <!-- serves: FR-10 -->

**成功时**：
```
✓ [动作完成] + [关键信息]
下一步：[后续动作]
```

**失败时**：
```
✗ [错误原因]
修复：[可执行建议]
```

**部分成功/警告**：
```
⚠ [警告信息] + [已完成部分]
建议：[如何处理警告]
```

### 2. 错误信息结构 <!-- serves: FR-10 -->

```typescript
{
  success: false,
  code: 'REQBOARD_SPECIFIC_ERROR', // 结构化错误码
  reason: '人话解释原因',
  fix_hint: '如何修复（可执行命令或操作）',
  fallback: '替代方案（如"用看板确认按钮"）'
}
```

## 工具反馈规范（12 个工具，精简后） <!-- serves: FR-10 -->

### 1. reqboard_capture（立项，精简后唯一入口） <!-- serves: FR-10 -->

**description 优化**：
```
立项（一次完成「立项四问」+创建+绑定）。识别到值得立项的新工作时调用。弹框四问：需求名称（可选候选/自定义）、类型、难度、文档位置。用户作答即立项。弹框不可用时自动降级到内部 create 路径（不暴露为独立工具）。
```

**render 优化**：
```typescript
// 成功
✓ 已立项：REQ-abc123《需求名称》（用户确认）
分类：feature | 难度：standard | 文档：docs/requirements/REQ-abc123/
下一步：reqboard_move(to='brainstorming') 开始需求分析

// 未立项（用户拒绝）
✗ 用户选择"不需要立项"
建议：如确需立项，重新调用并调整 title_options

// 弹框不可用
⚠ 弹框通道不可用（fallback=board）
替代：在对话中取四问值，再调 reqboard_create 手工立项
```

---

### 2. reqboard_status（查询） <!-- serves: FR-10 -->

**description 优化**：
```
查询本窗口 reqboard 绑定状态：是否已绑定进行中需求、当前状态、可推进动作、条款接收状态、设计文档登记态。识别到新工作想立项前先自查；看板链接可点击跳转。
```

**render 优化**：
```typescript
// 已绑定
需求：REQ-abc123《标题》| 状态：design | 分类：feature
可推进：decomposing / brainstorming / canceled
设计文档：5 份已登记，0 份已确认
[查看看板] /dashboard#pmboard?req=REQ-abc123

// 未绑定
本窗口无绑定需求
可立项：reqboard_capture（推荐）或 reqboard_create
```

---

### 3. reqboard_move（推进状态） <!-- serves: FR-10 -->

**description 优化**：
```
推进需求状态（项目看板泳道）。里程碑处自行推进（方案定→decomposing，开工→implementing，交付→accepting）；取消/归档需人工操作。写清 reason（供复盘）。先用 reqboard_status 查可推进动作。
```

**render 优化**：
```typescript
// 成功
✓ 需求已推进：design → decomposing
REQ-abc123《标题》
理由：[用户提供的 reason]
下一步：reqboard_submit(kind='plan') 提交拆分计划

// 失败（产物门禁）
✗ 推进被拒：design 产物未确认
缺口：5 份设计文档已登记，但未经人确认
修复：调 reqboard_ask_confirm(target='artifact', kind='design') 请人确认

// 失败（人工闸门）
✗ 推进被拒：归档需人工操作（代码级拒绝）
替代：在看板点"归档"按钮
```

---

### 4. reqboard_submit（提交产物/计划） <!-- serves: FR-10 -->

**description 优化**：
```
提交阶段产物（kind 区分五类）。requirement=需求文档（brainstorming）、design=设计文档登记（design，path 缺省扫 design/ 全目录）、plan=拆分计划（decomposing）、verification=验收材料（implementing/accepting）、archive=归档材料（archived/done）。提交后请人确认/审核。
```

**render 优化**：
```typescript
// kind=design 成功
✓ 已登记 5 份设计文档（kind=design）
architecture.md / data-model.md / interfaces.md / test-cases.md / use-cases.md
下一步：reqboard_ask_confirm(target='artifact', kind='design') 请人确认

// kind=plan 成功
✓ 已提交拆分计划（10 张任务卡）
路径：docs/requirements/REQ-abc123/decomposition.md
下一步：reqboard_ask_confirm(target='plan') 请人批准计划

// 失败（孤儿章节）
✗ 提交被拒：设计文档含孤儿章节（design_orphan）
缺口：architecture.md §"某某设计" 未标注 serves: FR-x
修复：给每个二级章节补 serves 标注

// 失败（门禁）
✗ 提交被拒：拆分计划未含任务表（plan_empty）
修复：在 decomposition.md 补任务表（key/title/phase/side/depends_on/acceptance/implementation）
```

---

### 5. reqboard_ask_confirm（确认门） <!-- serves: FR-10 -->

**description 优化**：
```
关键确认（原子化：确认→落章→推进）。两条路径：①弹框路径（不传 evidence）：把问题弹给用户，肯定项→自动落章并推进；②文字证据路径（传 evidence）：把用户在 ask_user_question 中的明确答复原文落成确认。适用：阶段产物确认（target=artifact, kind=requirement/design/plan/verification/archive）、批准拆分计划（target=plan）。
```

**render 优化**（含回执查询）：
```typescript
// 成功（弹框路径，用户确认）
✓ 用户已确认设计文档
需求已推进：design → decomposing
下一步：reqboard_submit(kind='plan') 提交拆分计划

// 未确认（用户要求修改）
✗ 用户选择"需要修改"
反馈：[用户输入的修改意见]
处理：按意见修改后重新提交 reqboard_submit + reqboard_ask_confirm

// 挂起（超宽限未作答）
⚠ 弹框已投递，等待人工作答（ticket=pc-abc123）
查询：reqboard_confirm_receipt(ticket='pc-abc123') 取回执

// 查询回执（pending 后）
const receipt = await tools.reqboard_ask_confirm({
  requirement_id: 'REQ-abc123',
  target: 'artifact',
  kind: 'design',
  ticket: 'pc-abc123' // 传 ticket = 查询模式
});
// receipt.confirmed = true/false（以台账为准）
// receipt.user_feedback = 用户反馈（未确认时）

// 弹框不可用
⚠ 弹框通道不可用（fallback=board）
替代：在看板点"确认设计"按钮
```

---

### 7. reqboard_accept_sheet（验收单） <!-- serves: FR-10 -->

**description 优化**：
```
验收单逐项弹框验收（原子：弹框→记录裁决→未过项自动返工）。每次弹一批待验项（batch_size 默认 5，≤10），选项：通过/改进/其他。仍有待验项时再次调用从断点继续。subagent/无 UI 通道时返回 fallback=board。
```

**render 优化**：
```typescript
// 本批通过
✓ 本批 5 项全部通过
剩余待验：3 项
下一步：reqboard_accept_sheet 继续验收

// 本批有未过项
⚠ 本批 2/5 项未过，已自动返工
返工卡：t-abc123, t-def456
用户意见：[逐项意见]
处理：按意见修改后，系统会自动重新验收

// 全部完成
✓ 验收完成，全部通过
需求已归档：REQ-abc123
下一步：reqboard_submit(kind='archive') 准备归档材料
```

---

### 8. reqboard_decompose（拆分落库） <!-- serves: FR-10 -->

**description 优化**：
```
拆分落库（plan mode 的执行端）：把已获人批准的拆分计划写成任务卡。默认不传 tasks = 直接落库批准的计划；传 tasks 则 key 集合必须与批准的计划一致。前置条件：需求属于本窗口、处于需求分析/拆分/实施态，且计划已由人批准。
```

**render 优化**：
```typescript
// 成功
✓ 已落库 10 张任务卡
需求状态：decomposing → implementing
任务映射：t1→t-abc123, t2→t-def456, ...
下一步：reqboard_task_run 推进父卡

// 失败（计划未批准）
✗ 拆分被拒：计划未由人批准
修复：调 reqboard_ask_confirm(target='plan') 请人批准计划

// 失败（key 不一致）
✗ 拆分被拒：传入 tasks 的 key 集合与批准计划不一致
批准的：[t1, t2, t3]
传入的：[t1, t2, t4]
修复：确保 tasks 参数与批准计划完全一致，或不传 tasks（落库批准的计划）
```

---

### 9. reqboard_task_move（任务推进） <!-- serves: FR-10 -->

**description 优化**：
```
推进任务状态（todo→in_progress→integration/testing→in_review→done）。开工时移到 in_progress（自动开一段执行记录），完成时移到 done。只有取消任务/复活已取消任务是人工闸门。可选修订本卡的验收标准（acceptance 参数）。
```

**render 优化**：
```typescript
// 开工
✓ 任务已开工：t-abc123《任务标题》
状态：todo → in_progress
任务卡：docs/requirements/REQ-xxx/tasks/t-abc123.md
下一步：实施本卡，完成后 reqboard_task_move(to='done')

// 完成
✓ 任务已完成：t-abc123《任务标题》
状态：in_progress → done
全部任务完成：需求自动进入验收

// 失败（人工闸门）
✗ 推进被拒：取消任务需人工操作
替代：在看板任务卡点"取消"按钮
```

---

### 10. reqboard_task_report（任务汇报） <!-- serves: FR-10 -->

**description 优化**：
```
任务完成汇报：把"做了什么"结构化落到任务卡文档。传入 summary / completed / files_changed / next_step。重复汇报幂等（追加新段落但不重复登记产物）。前置：任务属于本窗口绑定的需求。
```

**render 优化**：
```typescript
// 成功
✓ 已汇报任务：t-abc123《任务标题》
汇报内容：
  完成项：3 条
  改动文件：5 个
  下一步：[用户提供的 next_step]
任务卡：docs/requirements/REQ-xxx/tasks/t-abc123.md（已更新）

// 幂等
⚠ 本次汇报已追加（第 2 次汇报）
任务卡：已更新，未重复登记产物
```

---

### 11. reqboard_task_run（链投递，本需求核心） <!-- serves: FR-1, FR-8, FR-10 -->

**description 优化**：
```
推进父卡的自动实施链（投递后台 run，立即返回）。链在后台跑（父卡开工/子卡执行/收尾/rollup），完成时收到通知。用 reqboard_run_status 查询进度，用原生 job_output/job_kill 读取/终止。重复投递拒绝（幂等）。
```

**render 优化**：
```typescript
// 成功
✓ 已投递后台：job_id=reqboard-1, run_id=uuid-xxx
链在后台跑，完成时会收到通知
查询进度：reqboard_run_status(run_id='uuid-xxx')
读取/终止：job_output / job_kill（原生工具）

// 失败（幂等拒绝）
✗ 投递被拒：该需求已有 run 在跑（runId=uuid-yyy）
既有 job：reqboard-2
查询：reqboard_run_status(run_id='uuid-yyy')

// 失败（依赖缺失）
✗ 投递被拒：后台任务系统不可用（ctx.jobs=undefined）
原因：profile 配置错误或 DSH 版本过旧
排障：检查 config/cordis.yml 的 jobs 配置
```

---

### 12. reqboard_task_execute（兼容别名） <!-- serves: FR-8, FR-10 -->

**description 优化**：
```
【兼容别名】等价于 reqboard_task_run。推进父卡的自动实施链（投递后台 run，立即返回）。参数、返回值、语义与 reqboard_task_run 完全相同。
```

**render 优化**：与 reqboard_task_run 相同。

---

### 13. reqboard_run_status（本需求新增） <!-- serves: FR-2, FR-8, FR-10 -->

**description 优化**：
```
查询运行态快照（只读）：runId / 当前步 / 在跑子卡 / 下一步 / job 状态 / 暂停原因。无在跑 run 时返回终止态与原因。不传参数查本窗口绑定需求。不消费 job 读游标。
```

**render 优化**：
```typescript
// 运行中
需求：REQ-abc123
运行：uuid-xxx | 状态：running (job: running)
步号：5 / 20
在跑：t-sub2
下一批：t-sub3, t-sub4
心跳：1 秒前

// 已完成
需求：REQ-abc123
运行：uuid-xxx | 状态：completed
stopped: max_steps_reached
说明：跑了 20 步上限，需续跑
续跑：reqboard_task_run(task_id='t-parent1')

// 无运行记录
需求：REQ-abc123 无运行记录
需求状态：implementing（未投递或已完成）
```

---

### 14. reqboard_task_status（本需求新增） <!-- serves: FR-2, FR-10 -->

**description 优化**：
```
查询任务执行状态和进度。传入 task_id（父卡或子卡）。返回：状态 / 进度 / workflow run 信息 / 在跑子卡 / 下一步 / 错误。
```

**render 优化**：
```typescript
// 父卡运行中
任务：t-parent1《任务标题》| 状态：in_progress
进度：3/10 子卡完成
在跑：t-sub4
下一步：t-sub5, t-sub6（写集并行）

// 父卡完成
任务：t-parent1《任务标题》| 状态：done
完成时间：2026-09-25 15:30
所有子卡：10/10 完成

// 子卡失败
任务：t-sub2《子卡标题》| 状态：failed
错误：schema 校验失败（产出不符合格式）
尝试次数：2/3
下一步：修复后会自动重试
```

---

## 实施清单 <!-- serves: FR-10 -->

**精简后 12 个工具**，每个需要修改 3 个文件：

1. **src/tools/XxxTool/index.ts** - 更新 description
2. **src/tools/XxxTool/render.ts**（或 index.ts 内的 render）- 优化 render 逻辑
3. **src/tools/XxxTool/errors.ts**（或用例层）- 统一错误码与文案

**验收**：
```bash
# 单测（render 逻辑）
npx vitest run tests/tools/render.test.ts

# 集成测试（完整调用）
npx vitest run tests/integration/tool-feedback.test.ts

# 人工抽查
cd packages/web/dsh-pmboard
npm run dev  # 启动 profile
# 在 agent 窗口调用 5 个工具（成功+失败各一次），评分
```