# t-3e11bf 测试与门禁收口 + 文档漂移同步

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
测试与门禁收口 + 文档漂移同步

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：doc

## 得到什么结果

npx vitest run 全绿（新增失败 0；既有他人债逐条列明来源需求）且 npx tsc --noEmit -p tsconfig.json 无新增错误；
grep 判据落成可跑命令：reqboard-workflow.md 的闸门表与 GateCatalog.ts / ArtifactSpec.ts 逐条一致（本卡汇报 1 已落）；
立项硬化语有单测锁定：npx vitest run tests/capture.test.ts 通过，且断言含「第一个工具调用必须是 reqboard_capture」「本条不立项」「不许沉默」。
说明（正位，2026-09-20 用户裁定）：需求级线上走查（AC-7.1 立项、AC-11.2 G1、两处留痕各 +1）不在本卡承载——改由 accepting 阶段的 verification 证据采集，验收义务不变（见 requirement.md §7.3.2 与 AC-11.2）。

## 实施方案（implementation）
补测试与 E2E 证据；更正 reqboard-workflow.md:17 与 ArtifactSpec.ts:34 注释

## 上游产出摘要（dependsSummary）
- 修投递死链路：AgentDeliverer 统一投递形状
- H2 压缩接线：接入 isolateNodeContext（含自足判定与开关）
- H3 注入器 + 难度取词映射（promptDifficulty→light/heavy）
- 立项 pm 专有弹框工具 reqboard_capture + 文案改造
- 看板通道 B：确认即推进 + 链侧投递

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T06:41:12.888Z，窗口 session-878da638-a076-4266-ae40-70a2390060f2）

t10 第一段完成（任务进行中）：文档漂移同步 + 全量门禁收口。两类漂移一条已更正（指南把「批准拆分计划」挂错边且漏了 G3）、一条已消解（ArtifactSpec 的「五道/四条」注释随 t2 迁移一并重写）；全量 vitest / tsc / 客户端构建与哨兵校验全部通过，与 pristine 基线 diff 新增失败 0。

### 完成项

- 更正 docs/guides/reqboard-workflow.md:17：重写为「人工闸门 = 四道产物确认门 + 取消」，显式给出四条边（brainstorming>design / design>decomposing / decomposing>implementing / accepting>archived）并注明事实源（GateCatalog.ts + HUMAN_ONLY_REQ_TRANSITIONS，由测试互锁）；同时记录"本节此前两处错"
- 核实并标注：ArtifactSpec.ts 的「五道人工确认门」注释已随 t2 的门表迁移一并重写（现只剩再导出说明），判据 grep "五道人工确认门" → 0 命中
- PRD §7.4 漂移表两条状态改为「已更正 / 已消解」并注明时点；D7 备注按用户指正改写（归档不是独立人工门）
- 门禁收口：tsc 无新增错误（仅基线 update-task-card.ts 一条）；全量 npx vitest run 与 pristine HEAD 基线逐条 diff → 新增失败 0（14 vs 15）；pnpm build:client + verify-client 通过（bundle=232395 bytes，关键符号齐全，styles.ts 括号配对）
- 漂移判据落成可跑命令：grep 指南中错误边写法 → 0 命中；grep ArtifactSpec 的「五道…」→ 0 命中

### 改动文件

- `docs/guides/reqboard-workflow.md`
- `docs/requirements/REQ-e3b6a0/requirement.md`

### 下一步

t10 余项：AC-11.2 E2E（:13080 真实走一次 G1，需重启加载新代码——会中断本会话，待用户确认后执行）；t8 立项 pm 弹框仍等 REQ-99f5fe 停手

---
## 汇报 2（2026-09-20T07:20:51.247Z，窗口 session-878da638-a076-4266-ae40-70a2390060f2）

E2E 走查准备就绪（本段为重启前的交接记录，重启后按此继续）：profile 已临时开启 NODE_ISOLATION 并写好续跑标记，接下来一次重启同时加载 REQ-e3b6a0 新代码，然后在 :13080 做一次真实立项走查，核验两个留痕文件各 +1。

### 完成项

- profile 补丁临时开启压缩：.dsh-data/profiles/agent-dh/cordis.patch.yml 的 dsh-pmboard 段加 nodeIsolation: true（备份 cordis.patch.yml.bak-nodeIsolation-e2e-2026-09-20T07-20-28-690Z）；**走查完成后必须改回 config: {}**（D1：链先开、压缩后开）
- 写好续跑标记 .dsh-data/state/pending-resume.json（origin_agent_id=session-878da638-a076-4266-ae40-70a2390060f2，checkpoint_branch=null → 未做 wip 检查点，故**不需要也不应调 self_finalize**）
- **E2E 基线已落 /tmp/e2e-t10-baseline.json**：prompt-injection-log.json 存在且已满 500 条（ring cap），最后一条 at=1789888833860 / windowKey=session-878da638… / stage=implementing / routeKey=implementing/light/feature / charCount=1593；node-isolation-log.json **不存在**（NODE_ISOLATION 此前恒关）。故「各新增一条」的判据是：注入日志的**最后一条发生变化**（计数不变），隔离日志**首次生成且含至少 1 条**
- 走查步骤（重启后执行）：① 在 :13080 另开一个**新会话窗口**（不要用绑定中的本窗口做压缩试验田）提一个新工作意图；② agent 调 reqboard_capture 弹三问，人作答（需求名称/类型/难度）；③ 核验四项：需求已创建且 sourceSessionId=新窗口、状态 brainstorming；两处留痕各 +1；新窗口在**没有新用户消息**的情况下产出 docs/requirements/<新REQ>/requirement.md
- 风险与已知后果：NODE_ISOLATION 开启后，「绑定窗口 + 新用户消息 + 未结算过的可注入阶段」会触发**遗留隔离路径**的整段上下文替换（每阶段一次）。本窗口（实现中）在下次收到用户消息的回合结束时也会被替换一次——届时上下文只剩系统段 + 节点输入包，本任务卡与续跑消息会保留，工作产物都在磁盘上，可继续

### 改动文件

- `.dsh-data/profiles/agent-dh/cordis.patch.yml`
- `.dsh-data/state/pending-resume.json`

### 下一步

重启（launchctl kickstart -k com.pi-investment.dsh）→ 用户在浏览器回到本会话触发续跑投递 → 按上面五步做走查 → 把两处留痕与需求文档路径记进 t10 验收材料，并把 nodeIsolation 改回 {}。

---
## 汇报 3（2026-09-20T07:47:38.342Z，窗口 session-878da638-a076-4266-ae40-70a2390060f2）

E2E 走查发现"立项该弹不弹"的真因不在提示词缺失、也不在链路断线，而在"发起"这一步被交给了模型自由裁量：实测窗口的登记/注入全正常，但模型把"修复 FR-6 任务状态机"这种明确工作意图判成"对当前审查的追问"，直接作答不弹框。这一步把立项提示从"请你判断可能值得立项"改成"必须显式裁定"——判不准按值得立项处理、值得立项时本回合第一个工具调用就是立项弹框、不立项必须在回复首行写明理由（沉默不再是选项），并补了回合消费留痕与防软化单测。

### 完成项

- 实测定位（转录逐条核对，窗口 session-361c2879 / 15:18–15:30）：CaptureHook 登记 ✓、pendingCapture 命中 ✓、capturePromptForMessage 针对性段注入 ✓（turn 2/3/4 system/message 均含「检测到用户新输入」）；但 17 次 tool/call（PTC 展开 35 次子调用：read 28 / grep 7）零次 reqboard_capture——提示已到位、模型未执行
- 根因判定：FR-7 只解决"立项框走 pm 通道"，未解决"什么时候必须弹"；原文案二元自由裁量 + 不弹框零后果（无拒绝/无留痕/无重试）
- 硬化 capturePromptForMessage：必须显式裁定（判不准按值得立项处理）／值得立项时本回合第一个工具调用即 reqboard_capture／不立项时回复首行写明「本条不立项：<理由>」／判据锚定"修复/改/新增/实现/重构/优化/补充/调研/做/支持 + 具体对象"，并声明"夹在提问里也算"
- 硬化 captureGuidanceText（静态引导）：拿不准按"值得"处理，弹框问用户（框里可选"不需要"）比沉默安全
- CaptureHook turn/end：pending 消费时留痕（提示存活时长）；注释写明 PTC 下 tool/call 一律呈现为 run_code、无法从 toolTrace 判定是否调过工具，故不做"漏执行"误判
- 单测锁定硬化语防再软化：tests/capture.test.ts 新增 1 例（第一个工具调用必须是 reqboard_capture／本条不立项／不许沉默／静态引导含"弹框问用户"），本文件 23 通过
- 门禁实测：npx vitest run 全量 13 失败 1383 通过——逐条核对全部为既有他人债（REQ-a8d582 验收覆盖 5 条 / REQ-327bdf 的输出契约·工具面·层边界·数值卫生 5 条 / typecheck 基线 1 条 / size-budget index.ts 1 条 / client-view 1 条），本次新增失败 0；npx tsc --noEmit 仅基线 1 条（TaskExecuteTool/update-task-card.ts TS6133）
- 需求文档同步：FR-7 增第 8 条（触发时机硬化）+ 新增 §7.3.2 记录实测证据、根因、硬化口径与"仍不在范围"的代码侧强制机制

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/capture-section.ts`
- `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`
- `packages/pages/dsh-pmboard/tests/capture.test.ts`
- `docs/requirements/REQ-e3b6a0/requirement.md`

### 下一步

重启 :13080 加载新代码（本会话会中断，lifecycle 自动续跑），随后在**新窗口**提一个工作意图做立项走查（AC-11.2 步骤②③）；走查通过再交 accepting。若走查仍不弹，则升级为代码侧强制机制（需人拍板）。

---
