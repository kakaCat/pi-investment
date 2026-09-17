# REQ-2e9473 技术设计与实施计划

**需求**：reqboard 执行链加固：确认弹框原子化 + 实施防假完成 + 拆分幂等 + 产物自动登记 + 实施卡与验收单
**当前阶段**：planning（技术设计）
**上游需求文档**：[requirement.md](./requirement.md)（v3.1，六工作流 W1-W6）

---

## 1. 技术设计概览

全部改动收敛在 `packages/pages/dsh-pmboard/` 插件内部，不动 harness 内核。两个关键技术风险已排除：

- **弹框通道**：harness 开放 `ctx.userQuestions` 服务接缝（@deepseek-ai/dsh-user-questions，UserQuestionService.ask(request)），插件工具可直接调用弹框 UI。注意其约束：owned child/subagent 无权发问（DELEGATED_CALLER），ask_confirm 须捕获该错误并降级提示"请到看板点确认按钮"。
- **会话事件可见性**：capture-hook 已订阅 `session/event` 全量事件（user/message、tool/call、turn/end），工具痕迹跟踪与超时提醒都有事件源。

## 2. 现状代码锚点

| 文件 | 现状 | 本需求改动 |
|------|------|-----------|
| `src/shared/protocol.ts` | 状态机/闸门/PlanTask/StageArtifact | +PlanTask.implementation、+VerificationSheet（验收单数据模型）、+返工任务关联字段 |
| `src/host/agent-tools.ts` | 13 个 reqboard_* 工具；decompose 守卫 696-701 行有缺口 | decompose 幂等、task_move 凭证门/任务卡送达、plan_submit 校验、verify_submit 验收单、新增 reqboard_ask_confirm |
| `src/host/artifact-gates.ts` | 产物登记+两级闸门 | confirm_artifact 文字确认核验（evidence 须为真实用户消息原文） |
| `src/host/capture-hook.ts` | 立项捕获+阶段提示词注入（onStagePrompt 回调） | +工具痕迹跟踪（tool/call 计数）、+里程碑超时提醒 |
| `src/host/rollup.ts` | R1/R2/R3 派生推进 | R2 不变；返工回路打回 implementing 走人工门（verify-rework 已有语义） |
| `src/host/store.ts` | 台账持久化 | 验收单版本存储 |
| `src/client/view.ts / stage-panel.ts / dom.ts / api.ts` | 详情页/阶段面板/事件委派/API | 验收单逐项勾选 UI、⏳等待确认标记、文档记录区 auto_discovered 标记、blockers 展示 |

## 3. 四视角技术设计

### 3.1 UI 视角

1. **验收单界面**（accepting 阶段面板主体）：逐项列表 = [✓/✗ 勾选] 验收标准 + 证据链接 + 意见输入框；底部"提交验收结论"。有不通过项 → 显示"将打回实施并生成返工任务 N 项"预览。
2. **⏳等待确认标记**：需求卡+详情头部，产物已登记未确认时显示（三通道确认的可见性兜底）。
3. **文档记录区**：auto_discovered 产物带"自动发现"徽标；task_output 产物带任务 id 链接。
4. **blockers 展示**：rollup 阻塞时详情页顶部横幅"未进验收：N 个任务未完成（清单）"。

### 3.2 前端视角

- `api.ts`：新增 `submitVerdicts(reqId, sheetVersion, verdicts)` 调用；`stage-detail` 返回体扩展验收单数据。
- `stage-panel.ts`：accepting 面板渲染验收单（逐项 checkbox + 意见框 + 版本切换 v1/v2…）。
- `view.ts`：buildReqDetail 集成 ⏳标记、blockers 横幅、文档记录区徽标。
- `dom.ts`：验收单勾选/提交的事件委派（data-action="submit-verdicts"）。

### 3.3 后端视角

1. **W3 幂等**：decompose 守卫补 decomposing/implementing 拒绝 + "该需求已有未取消任务"检查（返回已有任务清单）。
2. **W5 实施卡**：protocol PlanTask 加 `implementation`；plan_submit 校验（缺 implementation 或 acceptance 无可验证锚点 → 拒）；decompose 拒落薄卡；task_move→in_progress 返回任务卡全文。
3. **W2 凭证门**：capture-hook 维护 windowKey→tool/call 计数（按任务 claimedAt 分段）；task_move→done 校验 ①有 task_report ②开工后有 edit/write/bash 痕迹 ③距上次本窗口 done ≥60s（批量关闭节流）④pages 任务构建新鲜度（lib/client.js mtime > src 最新 mtime）。
4. **W1 ask_confirm**：新工具内部 `ctx.userQuestions.ask()` → 肯定答复 → confirm_artifact + move 原子执行；捕获 DELEGATED_CALLER/CALLER_NOT_LIVE → 降级提示看板通道。move 闸门拒绝返回 `gate_question` 结构；submit 类工具 note 改指向；capture-hook 超时提醒（产物登记未确认 >30min 注入）。
5. **W1 文字确认核验**：capture-hook 维护窗口最近用户消息环形缓冲；confirm_artifact 的 evidence 须命中缓冲内真实原文（弹框答复自动登记，免引证）。
6. **W4 产物登记**：`syncReqArtifacts(reqId)` 扫 REQ 目录补登（auto_discovered）；渲染详情前调用；task_report files_changed 上浮 kind=task_output；verify_submit evidence 路径存在性校验；archive_submit 漏登警告。
7. **W6 验收单**：protocol 加 `VerificationSheet { version, items[{ id, source(taskId|'requirement'), criterion, evidence[], verdict?, opinion? }] }`；verify_submit 从任务 acceptance + 需求验收标准生成；逐项裁决持久化；有不通过 → 需求回 implementing + 每未过项生成返工任务（linkedTo 原任务 + 意见）；重交只含未过项，版本 +1。

### 3.4 测试视角

- 单测（vitest，host 层纯函数为主）：decompose 幂等、薄卡拒落、done 凭证门四类拒绝、文字确认核验真/伪、验收单生成与返工回路、目录扫描补登幂等。
- **故障注入**（对应五类事故复现）：A 模拟弹框确认→断言落章+推进原子完成；B 重复 decompose→断言拒绝且任务数不变；C 25ms 速通→断言 done 被拒；E 目录丢新文件→断言详情 HTML 含该文件；F 薄卡提交→断言 plan_submit 被拒。
- 回归：`npx vitest run` 全绿 + `pnpm build:client` + verify-client-build OK + :13080 实机走一遍"立项→…→验收单逐项确认"。

## 4. 任务表（19 项）

> 说明：本需求自身仍按现行工具约束提交（plan 带任务表）；t17 落地后，后续需求的任务卡改在 decomposing 阶段创作。

| key | 标题 | phase | side | depends_on | acceptance |
|-----|------|-------|------|------------|------------|
| t01 | decompose 幂等守卫（W3） | implement | backend | - | 重复 decompose 被拒并返回已有任务清单；vitest 用例通过（故障注入：任务数不变） |
| t02 | rollup 阻塞 blockers 字段（W3） | implement | backend | - | 有未完成任务的 verify_submit/task_move 返回含 blockers 任务清单；单测覆盖 |
| t03 | PlanTask.implementation 字段 + plan_submit 校验（W5） | implement | backend | - | 缺 implementation 或 acceptance 空话的计划提交被拒；任务表 DAG 提交时校验（前向引用/不存在依赖打回，事故 G）；合法计划通过；单测覆盖 |
| t04 | decompose 薄卡拒落 + 开工任务卡送达（W5） | implement | backend | t03 | 薄卡落库被拒；task_move→in_progress 返回含 acceptance/implementation/context 全文 |
| t05 | capture-hook 工具痕迹跟踪（W2 前置） | implement | backend | - | tool/call 事件按窗口计数并可按任务开工时间分段查询；单测覆盖 |
| t06 | done 凭证门三件套（W2） | implement | backend | t04, t05 | 无 report/无工具痕迹/60s 内连续 done 均被拒；pages 任务 lib/client.js 陈旧被拒；故障注入 25ms 速通被拒 |
| t07 | reqboard_ask_confirm 原子工具（W1 核心） | implement | backend | - | 弹框确认→落章→推进一次完成；选"需修改"不推进；subagent 调用降级提示看板通道 |
| t08 | 闸门问题卡 + 提交类工具 note 改指向 + stage-prompts 改指向（W1） | implement | backend | t07 | move 被拒返回 gate_question 可被 ask_confirm 直接消费；三处 submit note 含"下一步调 reqboard_ask_confirm" |
| t09 | 里程碑超时未确认主动提醒（W1） | implement | backend | t07 | 产物登记 >30min 未确认时绑定窗口收到注入提醒（注入留痕可查）；单测模拟覆盖 |
| t10 | 文字确认核验（W1 三通道③） | implement | backend | - | confirm_artifact evidence 伪造/找不到原文被拒；真实用户消息原文通过；弹框答复免引证 |
| t11 | REQ 目录产物自动发现（W4） | implement | fullstack | - | 新文件落 docs/requirements/<REQ>/ 后详情页文档记录区自动出现（带自动发现徽标）；重复扫描幂等 |
| t12 | 任务文件上浮 + evidence 存在性 + 归档漏登警告（W4） | implement | backend | t11 | files_changed 进需求级产物清单；伪造 evidence 路径被拒；archive 漏登返回警告清单 |
| t13 | 验收单数据模型 + verify_submit 生成逐项验收单（W6） | implement | backend | t04 | 提交后验收单含每任务验收标准+需求级标准逐项（含 evidence）；版本化存储；**挂起/续验状态持久化**（pending/passed/failed 逐项） |
| t14 | 验收单逐项确认 + 断点续验 + 返工回路（W6） | implement | frontend | t13 | ask_user_question 逐项弹框验收；发现问题可挂起（小修当场改留痕/大修打回生成返工任务）；修复后从断点继续且已过项不重弹；看板勾选为并行通道 |
| t15 | 故障注入与回归测试 | test | fullstack | t01-t14 | A/B/C/E/F 五类事故复现用例全绿；vitest 全套通过；build:client + verify-client-build OK |
| t16 | 文档同步（workflow-stages/RFC 014/工具描述） | doc | doc | t15 | 相关文档更新至新行为；阶段纪律文本与实现一致 |
| t17 | W7 阶段产物边界：plan_submit 任务表改可选 + decompose 承担任务卡创作 | implement | backend | t03, t04 | 不含任务表的计划可提交（技术设计一套文档）；decompose 接受创作型 tasks 并经拆分确认门确认；故障注入：planning 阶段尝试落库任务被拒 |
| t18 | W7 阶段职责规范落地：STAGE_PROMPTS 七阶段重写（brainstorming 升级为 superpowers 式方法论检查表）+ workflow-stages.md 规范固化 | implement | backend | t17 | STAGE_PROMPTS 七阶段内容与 requirement.md W7 逐字对齐；brainstorming 含九步检查表（上下文探索→范围评估→逐个弹框提问→2-3方案→分节确认→写文档→自查→审阅→推进）；workflow-stages.md 新增各阶段六要素规范 |
| t19 | W8 文档演进留痕与变更传播 | implement | backend | t11 | 文档 changelog 段强制（重登记时必填变更原因）；上游变更 → 下游文档标"待同步"并在推进/验收时警告；同步后销标；影响清单进时间线 |

DAG 关键路径：t03→t04→t06 / t13→t14→t15→t16；t07→t08→t09；t01/t02/t05/t10/t11 可并行。

## 5. 风险与应对

| 风险 | 应对 |
|------|------|
| ctx.userQuestions 在 subagent 场景不可用 | ask_confirm 捕获 DELEGATED_CALLER 降级提示看板通道；阶段纪律注明"subagent 执行的任务由父窗口负责确认" |
| done 凭证门误拦合法快速任务（如纯 doc 微调） | 工具痕迹含 write/edit（doc 任务也有写动作）；证据不足时错误信息指明缺哪项，不笼统拒绝 |
| 构建新鲜度检查跨平台 mtime 可靠性 | 只读文件 mtime 不修改；检查失败（文件缺失）时降级为警告而非硬拦 |
| 验收单 UI 工作量 | 会话侧 ask_user_question 多问题模式兜底，看板 UI 可分两批（先只读清单+整单通过/打回，再逐项勾选） |
| 16 任务较大 | 按 W3→W5→W2→W1→W4→W6 顺序实施，t01/t02 止血先行可独立交付 |

## 6. 验收标准（需求级）

同 requirement.md 第 4 节，另加：实机演示一条完整链路（立项→弹框确认→计划→拆分→实施（含凭证门拦截演示）→验收单逐项确认→返工→v2 验收→归档）。

---

**编写**：w-41e7e4cd ｜ **依据**：requirement.md v3.1 + w-b8de6c05 会话复盘证据 + host/client 源码调研（agent-tools.ts:696-701、capture-hook.ts、ctx.userQuestions 服务接缝、verify-submit 现状）
