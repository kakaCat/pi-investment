# REQ-ff20ca 实施计划

> 状态：待批准 · 类型：feature · 绑定窗口：w-24ded829
> 上游需求：[requirement.md](./requirement.md)（做什么/为什么以它为准；本文只管怎么做/谁做/怎么验）

## 1. 目标回顾（来自需求文档）

| # | 目标 | 交付重点 |
|---|---|---|
| **G-优先** | 确认门工具化 + 补 requirement 产物登记入口（需求 5.0 / 5.1） | **排最前**——它卡住流程本身 |
| G1 | 文档打开走官方 `sidebarRight` + `documentpreview`（会话框 + 看板） | 回路载体 |
| G2 | 自研弹窗整套删除，不留降级 | 消除第二套实现 |
| G3 | 阶段纪律工具化（要求 agent 用 `ask_user_question`） | 回路发起侧 |

## 2. 技术设计（四视角）

### 2.1 后端 / 数据（host）

**① 补登记入口：`reqboard_requirement_submit`（新 agent 工具）**

对称于 `reqboard_plan_submit`：

```
入参：requirement_id（缺省=本窗口绑定）、path（缺省 docs/requirements/<REQ>/requirement.md）、summary
行为：校验文件存在 → registerArtifact({stage:'brainstorming', kind:'requirement', path, registeredBy:agent})
      → 发飞书通知请人审阅（复用既有通知通道）
约束：文件不存在 → 明确报错；同 path 幂等（按 path 去重，registerArtifact 已有语义）
```

**② 会话确认落章：`reqboard_confirm_artifact`（新 agent 工具）+ 确认模型扩展**

```
入参：requirement_id、kind、evidence（用户在 ask_user_question 中的答复原文）
落库：artifact.confirmedAt = now()
      artifact.confirmedBy = { kind:'human', via:'session', evidence, sessionId }
```

- 看板既有接口 `POST req/artifact/confirm` 补写 `via:'board'`（**向后兼容**：老记录无 `via` 一律视为 `board`）
- 审计不变量：agent 不能"自称已确认"而不留痕——`evidence`（用户答复原文）+ `sessionId` 必须落库可查

**③ 门禁判定改造：`reqboard_move` 从"谁调用"改为"产物是否已确认"**

```
brainstorming → planning：
  若 requirement 产物已 confirmed（via 不限）→ 允许 agent 推进（by=agent，注明依据人的确认）
  若未确认 → 拒绝，提示"请先用 ask_user_question 请人确认，或让人在看板确认"
```

**内核不变**：仍然"必须有人确认"，agent 只是"在门已开启后执行推进"，不再是绕过门。

### 2.2 前端 / UI（client）

**④ sidebarRight 接线（G1/G2）**

```
文档点击 → sessionId（槽位注入 → 回退「当前会话」快照）
        → address = dsh-resource://file/session/<sid>/<path>   // 本地 file-address.ts，对齐官方 grammar
        → ctx.sidebarRight.openResource(address)                // 官方右栏 + documentpreview 渲染
```

- `ctx.sidebarRight` **必须声明 `inject`**（实测修正）：Cordis 4 不允许访问未声明的服务
  （报 `cannot get property "sidebarRight" without inject`），与"可选访问即安全"的假设相反。
  该服务由 web-app 随官方 UI 插件组提供、实测存在；声明后插件等待其就绪再激活。
- 删除：`doc-modal.ts` 整文件、`board-mount.ts` 旧弹窗段（含硬编码 `md·19:15`）、弹窗专用 CSS
- 保留：`marked` 与 `.dsh-pm-md`（`view.ts` 渲染需求卡描述仍需要）

**⑤ UI 可见性（确认来源）**

- 看板/卡面：产物确认后标注来源（看板确认 / 会话确认），让"谁在哪儿确认的"可见
- 复用既有「待确认」标识，不新造视觉体系

### 2.3 测试用例

| 用例 | 断言 |
|---|---|
| 登记幂等 | 同路径重复 `requirement_submit` 不产生第二条 artifact |
| 登记失败路径 | 文件不存在 → 报错且不写台账 |
| 会话确认落章 | `confirmedBy.via==='session'`、`evidence` 与传入一致、`sessionId` 落库 |
| 看板确认 | `via==='board'`；老记录（无 via）读取不报错 |
| 门禁未确认 | `move(to='planning')` 被拒 + 提示含 `ask_user_question` |
| 门禁已确认 | 两种来源（board/session）下 move 均放行 |
| 地址构造 | 相对路径 / `./` 前缀 / 反斜杠 / 空格中文 / 段编码对齐官方 grammar |
| 弹窗已删 | 全仓 grep 无 `openDocModal`；`doc-modal.ts` 不存在 |
| 阶段纪律措辞 | 各阶段 prompt 含"必须用 `ask_user_question`"（单测锁定防回退） |

## 3. 任务表

见 `reqboard_plan_submit` 的 tasks（t1..t8，粒度与依赖在此定死）。

## 4. 风险与对策

| 风险 | 对策 |
|---|---|
| session workspace 根 ≠ `docs/...` 相对路径基准 | t5 最小验证先行实测；不行则改传绝对路径或 host 侧富化 |
| `ctx.sidebarRight` 未加载 | t5 探测并 console 诊断；不引入降级分支（按 G2） |
| 门禁改造把闸门改松 | 判定条件仅从"谁调用"改为"产物已确认"；未确认仍硬拒；单测锁定两态 |
| 台账 schema 变更影响老数据 | `via/evidence` 均为可选字段，读取侧给默认值；单测覆盖老记录 |

## 5. 提交前自查

- [x] 无占位符（TBD/待定）
- [x] 任务间无矛盾（依赖：t3←t2；t4←t1,t2,t3；t6←t5；t8←t4,t6,t7）
- [x] 描述无模糊（每任务含可验证的 acceptance）
- [x] 范围未蔓延（严格对齐 requirement.md 的 G1/G2/G3 + 5.0/5.1）
- [x] 四视角齐备（后端/前端/UI/测试用例）
