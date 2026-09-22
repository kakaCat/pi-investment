---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 设计 · REQ-260922012924-2e29 修复立项四问测试同步与 docBasePath 断点并开启节点压缩

## 目标 `serves: FR-1, FR-2, FR-3, FR-4`

立项链路四处在代码层收口：capture-tool 测试与四问实现同步转绿；`requirementDocPath` 消费 `docBasePath`；`config/cordis.yml` 开启 `nodeIsolation`；reqboard API 暴露工作区根、看板以绝对路径打开与显示文档。可证伪：指定测试全绿 + state 端点返回 workspaceRoot + 启动日志 NODE_ISOLATION=true。

## 架构与改动面 `serves: FR-1, FR-2, FR-3, FR-4`

四处改动互不耦合，分属四层：①测试层 tests/capture-tool.test.ts；②application 纯函数 node-input-package.ts 的 requirementDocPath；③配置层 config/cordis.yml（插件 PluginConfig.nodeIsolation 字段已存在，仅填值）；④接口层 stages.handleState 增加 workspaceRoot 字段 + 客户端 open-doc/显示层拼绝对路径。台账 schema 零改动（路径仍存相对，根在读取侧解析）——这是用户反馈"我以为 docs/requirements/<REQ> 在会话工作区下，其实不是"的根治点：**存储相对、显示绝对**。

## FR-1 设计：四问测试同步 `serves: FR-1`

tests/capture-tool.test.ts 4 处断言从"三问"改"四问"：①`questions` 长度 3→4；②id 顺序 `['name','category','difficulty']` → `['name','category','difficulty','doc_location']`；③缺项回落时 defaultsUsed 含 `doc_location`；④AC-7.2 端到端断言同步。只改断言期望，不动用例与 capture-mapping（实现已正确，测试陈旧）。

## FR-2 设计：requirementDocPath 消费 docBasePath `serves: FR-2`

改动 `src/application/internal/node-input-package.ts:162` 的 `requirementDocPath`，签名不变 `(requirement: RequirementRecord | undefined) => string`。解析优先级：`docLinks.requirement`（显式链接，最高）→ `docBasePath` 拼接 → 缺省 `docs/requirements/<REQ>/`。拼接契约：①`<REQ>` 占位符全部替换为需求 id；②docBasePath **无** `<REQ>` 时追加 `<id>/` 子目录（防多需求撞同一 requirement.md，如 `docs/rfcs/` → `docs/rfcs/<id>/requirement.md`）；③尾部斜杠归一；④文件名恒 `requirement.md`。兼容：无 docBasePath 的老记录走缺省分支，输出与现状逐字节一致。

## FR-3 设计：开启 nodeIsolation 压缩开关 `serves: FR-3`

`config/cordis.yml` 第 127-129 行 dsh-pmboard 段 `config: {}` 改为 `config: { nodeIsolation: true }`（PluginConfig.nodeIsolation 字段与 nodeIsolationEnabled() 求值链已存在，config 优先于 env NODE_ISOLATION）。生效路径：start.sh 从模板补全活动配置 → launchd kickstart 重启 → 启动日志 `压缩开关 NODE_ISOLATION=true`。回滚：改回 false/删除该行再重启，即恢复 D1 前行为。预期行为：G0 门 requirement.md 未落盘 → H2 `skip(doc_not_ready)`（保护立项上下文）；后续节点（文档已落盘、轮次边界 idle、边界配对平衡）→ 真压缩，留痕 state/node-isolation-log.json。

## FR-4 设计：文档路径绝对化 `serves: FR-4`

服务端：`stages.handleState`（routes.ts:163，GET /dashboard/api/reqboard/state）响应增加两字段——`workspaceRoot: string`（绝对路径无尾斜杠，取 `deps.cwd ?? process.cwd()`，本实例 = /Users/yunpeng/pi-investment/agent-dh）与 `homeDir: string`（os.homedir()，供客户端 ~ 缩写）。客户端：①board-mount 缓存 state.workspaceRoot，`open-doc` 动作把相对路径拼为 `workspaceRoot + '/' + rel` 再调 `openDocInSidebar`（conversation-progress.ts 的调用点同样改）；sessionFileAddress 保留前导斜杠即官方绝对路径地址（dsh-resource://file/session/<sid>/Users/...），Host 按绝对路径读，不再依赖会话工作区。②阶段详情/产物面板的文档路径显示为绝对路径（`path.startsWith(homeDir)` → `~` 缩写）。③CaptureRequirement 回执 note 的"文档将存放在：{docPath}"同步输出绝对路径。降级：旧服务端无 workspaceRoot 字段时维持现状相对解析（显示降级，非失败，如实可见）。

## FR-5 设计：立项拒绝粘滞 `serves: FR-5`

两处改动 + 一处文案。①CaptureRequirement 的 `mapped.rejected === true` 分支：返回 notCreated 之前先经注入端口写拒绝留痕——`state/capture-rejections.json`（ring buffer 结构 `[{windowKey, at, title?}]`，上限 50 条原子写，与 isolation-trace 同款纪律）；该写操作在用例内 try/catch 降级（留痕失败不阻断"未立项"返回）。②`captureRequirement` 前置判定段（绑定/pending 检查旁）新增拒绝检查：同窗口 `now - at < 30min` 的拒绝记录存在 → 直接 `notCreated(note='用户已于 HH:MM 在弹框选择不立项，本次不再弹框；如需立项请明确告知')`，**不调 questions.ask**。③CaptureTool/prompt.ts 补一句纪律：调用超时/中断后不得立即盲目重弹——前置拒绝检查会兜底拦截。僵尸框本身（调用方死亡后弹框未收回）属 DSH 框架 userQuestions 层问题，本需求不修框架，但 ①② 使系统在僵尸框场景下行为仍正确。数据契约：`CaptureRejection = { windowKey: string; at: number; title?: string }`，TTL 语义由消费方判定（30 分钟），不设主动清理（ring buffer 自然淘汰）。

## 数据契约 `serves: FR-2, FR-4, FR-5`

FR-2：`RequirementRecord.docBasePath?: string`（已存在，protocol.ts:815）——基目录，可含 `<REQ>` 占位符，可有/无尾斜杠；`requirementDocPath` 输出 = 工作区相对 POSIX 路径，恒以 `requirement.md` 结尾。FR-4：`BoardState` 增加 `workspaceRoot: string`（绝对路径，无尾斜杠）与 `homeDir: string`（绝对路径）；客户端不持久化，每次 fetchState 随取随用。台账零迁移：所有存储路径保持相对，根仅存在于运行时解析层。

## 迁移与兼容 `serves: FR-2, FR-3, FR-4, FR-5`

FR-5 为纯增量（新 state 文件 + 新前置检查），无拒绝留痕时行为与现状完全一致。无数据回填：老需求记录无 docBasePath → FR-2 缺省分支输出不变；FR-4 纯增量字段，旧客户端读不到 workspaceRoot 不受影响（多字段忽略）。FR-3 为开关型变更：灰度即单实例直开（模拟盘环境），回滚路径 = 配置改回 + kickstart，30 秒内可逆。活动配置 .dsh-data/profiles/agent-dh/cordis.patch.yml 由 start.sh 从模板补全，不手改。

## 测试策略 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

FR-1：capture-tool.test.ts 断言更新后原 4 红转绿。FR-2：artifact-path.test.ts 新增 4 用例（缺省路径逐字节一致 / docBasePath 含 <REQ> / 不含 <REQ> 自动追加 id 子目录 / docLinks.requirement 优先级最高）。FR-3：nodeIsolationEnabled 已有单测覆盖 config 优先级（node-gates.test.ts 现状），新增实证 = 重启后启动日志断言（人工验收步）。FR-4：服务端 stages 路由测试断言 state 含 workspaceRoot/homeDir；客户端 file-address 测试断言绝对路径地址构造（前导斜杠保留）。FR-5：capture-tool.test.ts 新增 3 用例（rejected 分支写留痕 / 留痕写失败降级不阻断返回 / 前置检查命中近期拒绝不调 ask）。全量回归：`npx vitest run packages/web/dsh-pmboard`。

## 验收口径 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

①`cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/artifact-path.test.ts` 全绿；②`grep -A2 "id: dsh-pmboard" config/cordis.yml` 见 `nodeIsolation: true`，重启后 `grep "压缩开关" .dsh-data/state/launchd.out.log | tail -1` 见 `NODE_ISOLATION=true`；③`curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot, homeDir}'` 返回 agent-dh 绝对路径；④在工作区=dsh-pmboard 的会话（w-9faaac35）看板点开本文档链接能打开（修复前必现打不开）；⑤FR-5 专项：构造同窗口 30 分钟内拒绝留痕后调 reqboard_capture → 不弹框返回未立项（单测断言 questions.ask 未被调用）；⑥`npx vitest run packages/web/dsh-pmboard` 全量绿。
