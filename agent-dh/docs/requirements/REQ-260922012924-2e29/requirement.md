# REQ-260922012924-2e29 修复立项四问测试同步与 docBasePath 断点并开启节点压缩

> 类型：feature ｜ 难度：standard ｜ 立项窗口：w-9faaac35（investor）
> 来源：2026-09-24 本窗口走查立项链路（reqboard_capture → G0 后置链 → 文档查看）实测发现，用户裁定修复并开启压缩。

## 产品定义

立项链路（reqboard_capture → G0 闸门后置链 → 文档查看）的五处工程收口：四问口径测试同步、docBasePath 被文档路径推导消费、节点压缩开关开启（D1 第二步）、文档路径绝对化、立项拒绝粘滞。全部是 dsh-pmboard 包内的缺陷修复与既定开关落地，无新产品能力。

## 用户与角色

- **窗口 agent（主要使用者）**：立项/推进需求时依赖正确的测试防护、文档路径解析与压缩链行为；
- **人类用户（立项确认者）**：在四问弹框作答，需要"点不立项即终结"与"文档打得开、路径看得懂"的可预期体验。

## 边界

- **做**：①capture-tool.test.ts 三问→四问断言同步（含 doc_location 的 defaultsUsed 口径）；②`requirementDocPath`（node-input-package.ts:162）消费 `docBasePath`（占位符 `<REQ>` 替换）+ 单测；③`config/cordis.yml` 加 `nodeIsolation: true` 并重启验证链行为；④文档路径绝对化：API 暴露 workspaceRoot + open-doc 拼绝对路径 + 面板显示绝对路径；⑤立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律。
- **不做**：不改压缩算法本身（`isolateNodeContext` 一行不动）；不改四问题目/选项/注入文案。
- **不做**：triage 遗留兼容路径删除（另一条独立工作线，本需求不含）；不修 DSH 框架层僵尸框收回（userQuestions 层，本需求让其场景下行为正确即可）。

## 功能点

### FR-1: 四问口径测试同步
capture-tool.test.ts 从"三问"断言更新为"四问"（含 doc_location 的题目数、id 顺序、defaultsUsed 回落口径），`vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts` 全绿。

### FR-2: docBasePath 被文档路径推导消费
`requirementDocPath()`（node-input-package.ts:162）在 `docLinks.requirement` 缺省时优先用 `docBasePath`（`<REQ>` 占位符替换为需求 id）拼路径；无 docBasePath 或默认 docs/requirements/<REQ>/ 时行为与现状一致。新增单测覆盖两分支。

### FR-3: 开启节点压缩开关
`config/cordis.yml` 的 dsh-pmboard 段加 `nodeIsolation: true`；重启后启动日志显示 `压缩开关 NODE_ISOLATION=true`；G0 门 requirement.md 未落盘时 H2 仍以 `doc_not_ready` 跳过并有留痕；不改压缩算法本身。

### FR-4: 文档路径绝对化
reqboard API 暴露服务端工作区根（FileDocRepository.workspaceRoot() 已预留）；看板/会话进度打开文档时用「根+相对路径」拼绝对路径构造 session 文件地址（dsh-resource 协议原生支持），任何工作区的会话均可打开；阶段详情/产物面板显示解析后的绝对路径（可 ~ 缩写）。

### FR-5: 立项拒绝必须粘滞（点"不立项"即终结，不得重弹继续）
现象（2026-09-21 用户现场反馈，台账+日志实证）：capture 弹框调用方超时/中断后弹框未收回成僵尸框；用户在僵尸框点"✖️ 不需要立项"的答复无消费者静默丢失；agent 不知已拒绝而重弹，需求最终被创建并推进。修复：①CaptureRequirement 的 rejected 分支把拒绝事实**落盘留痕**（窗口+时间戳，state 文件）；②reqboard_capture 弹框前置检查消费该留痕——同窗口近期（30 分钟内）已拒绝 → 直接返回未立项并如实说明，**不再弹框**；③工具提示词补纪律：capture 调用超时/中断后不得立即盲目重弹，前置检查会拦截。

## 验收判定（可证伪）

1. `cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts` **全绿**（当前 4 红）。
2. 新增单测：`docBasePath='docs/rfcs/'` → `requirementDocPath()` 返回 `docs/rfcs/<id>/requirement.md`；默认路径行为逐字节不变。
3. `config/cordis.yml` 含 `nodeIsolation: true`；重启后日志 `压缩开关 NODE_ISOLATION=true`；G0 门文档未落盘时 H2 `doc_not_ready` 跳过留痕。
4. `curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot, homeDir}'` 返回 agent-dh 绝对路径；在工作区=dsh-pmboard 的会话（w-9faaac35）看板点开文档链接能打开（修复前必现打不开）。
5. FR-5 专项：构造同窗口 30 分钟内拒绝留痕后调 reqboard_capture → 不弹框返回未立项（单测断言 questions.ask 未被调用）。
6. `npx vitest run packages/web/dsh-pmboard` 全量绿。

## 轻路径依据 + 单向升级

改动面小（一个测试文件 + 一个纯函数 + 一行配置 + 一处 API 字段与客户端拼路径 + 一个留痕文件与前置检查），**无新决策点**——docBasePath 语义、压缩开关、绝对路径诉求、拒绝粘滞均已在 2026-09-24 会话中由用户明确裁定。升级信号：出现第二个未定决策 / 动架构 / 新增子系统 / 改数据模型 → 立即停手升级重档，单向不降级。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |

> 🔴 **未被接收（5 条）**：FR-1、FR-2、FR-3、FR-4、FR-5

<!-- reqboard:marks:end -->
