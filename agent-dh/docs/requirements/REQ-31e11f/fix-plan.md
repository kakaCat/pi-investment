# REQ-31e11f 验收问题修复方案（v2 · 合并两轮验收）

- 日期：2026-09-15
- 背景：用户两轮验收共提出 11 项问题，要求统一解决
- 状态：方案待批准

## 一、问题总表（11 项，全部已核实到代码/台账）

### A 类 · 视觉/样式（4 项）

| # | 问题 | 根因（证据） | 修复 |
|---|------|------|------|
| 1 | 对话框上方流程图样式丢了 | **构建坏**：styles.ts `injectStyles()` 缺 `}`（t7 恢复漏）→ build PARSE_ERROR 失败 → lib/client.js 停留旧版。**已修**（补 } + 重建 20:46 + 服务重启 20:50） | 硬刷新验证；Step4 加固防复发 |
| 2 | 看板泳道图太丑 | 既有泳道样式简陋 + 缺样式放大 | Step3 美化 |
| 3 | 看板「立项/需求分析…」按钮丑、不统一 | `dsh-pm-stage-nav-btn` 在 styles.ts **无定义**（裸按钮） | Step2 补样式，复用 .dsh-pm-btn 体系 |
| 4 | 所有节点点开长得一样 | **`stage-panel.ts`（t6 新文件）用 58 个 class，styles.ts 一个都没定义** → 节点详情=无样式纯文本 | Step2 补 58 个 class，8 类节点视觉差异化 |

### B 类 · 功能/信息（7 项）

| # | 问题 | 根因（证据） | 修复 |
|---|------|------|------|
| 5 | 列表的窗口点击不跳转 | `jump-session` 处理器与 `jumpToSession` 都在；疑点：chip 被判 archived 渲染成灰 span（无 data-action），或 sourceSessionId 不在当前会话列表→missing | Step5 运行时定因；统一窗口 chip 可点性 + 失败给明确提示 |
| 6 | 看板文档记录不全 | `collectReqDocs`（view.ts:701）只读 docLinks/plan.path/archive.docs | Step5 并入 `req.artifacts` |
| 7 | 立项过程的文件应全部记录到文档里 | 同上：t4 登记的 pipeline 产物（requirement.md / plan.md / decomposition.md / tasks/*.md / verification.md）**没进文档区** | Step5 `collectReqDocs` 合并 artifacts，按 stage 排序展示 |
| 8 | 审批按钮都在折叠里，操作麻烦 | view.ts:803-812「实施计划/验收/归档」三个 `<details>` **默认折叠**（无 open），approve/verify/archive 按钮藏在里面 | Step6 审批入口**全部外置到卡片/详情正面**（详情头固定操作条） |
| 9 | 评论只记录 agent 的人机协同内容 | host 仅在状态转移/agent 工具时写 comment；**人的评论未采集** | Step5 采集人工评论入 comments（详情评论框 + 会话消息回流） |
| 10 | subagent 里完成的任务没被记录 | 台账 `REQ-31e11f` 的 t2-t9 **全为 todo**；subagent 是独立会话未绑定需求，完成未回写 | Step7 补 move t2-t9；建立 subagent 完成→看板回写机制 |
| 11 | 任务泳道图没有推进 | 同上：台账实际 t2-t9=todo（我汇报了但没 move） | Step7 立即补 move + 后续自动同步 |

## 二、修复方案（7 步）

| 步骤 | 内容 | 产出 |
|------|------|------|
| **Step1** 立即验证 | 硬刷新浏览器，确认构建修复已生效（#1） | 无改动 |
| **Step2** 补齐样式（核心） | 为 stage-panel.ts 58 个 class + view.ts 5 个补 CSS，8 类节点真差异化（统计卡/轨道/覆盖率条/追溯链/产物区/时间线） | styles.ts |
| **Step3** 视觉统一美化 | 泳道卡片、看板按钮、流程图节点统一 token（按钮复用 .dsh-pm-btn）；抽 pmboard 设计 token 段 | styles.ts + view.ts |
| **Step4** 构建加固 | build:client 产物校验（退出码+lib/client.js+关键 class）；styles 括号检查；发版走 restart-with-build.sh | scripts |
| **Step5** 信息补全 | ① collectReqDocs 并入 req.artifacts（#6/#7）② 人工评论采集（#9）③ 窗口 chip 跳转定因修复（#5） | view.ts / routes.ts / board-mount.ts |
| **Step6** 审批入口外置 | 详情头固定「待办操作条」：批准计划/验收通过/退回/归档 全部正面可见，不进折叠 | view.ts |
| **Step7** 台账同步 | ① 立即 move t2-t9 到 in_progress/done 反映实况 ② subagent 完成→看板回写机制（task_report 后自动 rollup，或窗口绑定传递） | host |

## 三、验收
- 视觉：4 处截图（流程图/泳道/按钮/节点详情 8 类）
- 功能：窗口点击跳转实测；文档区含全部 pipeline 产物；审批按钮正面可见；人工评论入库；subagent 任务在看板可推进
- 台账：t2-t9 状态与实况一致

## 四、说明
- #10/#11 是流程性缺陷：subagent 独立会话未绑定需求 → 完成不回写。本轮先补数据（move），机制在 Step7 落地（RFC 015 的窗口-需求绑定可复用）。
- node-diff worktree 已在 main，无需合并（其任务节点差异化与样式齐全）；仅剩文档收尾。
