# reqboard 立项弹框（capture）排障指南

> 来源：REQ-f6307c（2026-09-21）。适用症状：用户在 unbound 窗口发了工作意图消息，但立项弹框（reqboard_capture）没弹。

## 第一原则：先查诊断文件，不要只看 stdout

**可靠观测面**：`agent-dh/.dsh-data/state/reqboard-capture-diag.log`

```bash
tail -f agent-dh/.dsh-data/state/reqboard-capture-diag.log
```

⚠️ **不要只依赖 stdout/控制台日志**（REQ-f6307c 的核心教训）。stdout 在以下情形全部蒸发：

- launchd 未接管当前进程（被外部 shell 手工 `start.sh` 拉起）
- 进程由 `start.sh 2>&1 | tail -5` 这类管道拉起、reader 退出后 stdout 成死管道
- 查错日志路径：launchd 配置的真实路径是 `.dsh-data/state/launchd.out.log`，不是 `~/Library/Logs/`

判别进程 stdout 是否死管道：`lsof -p <pid> -a -d 1,2`——显示 PIPE 且对端无进程即死管道。

## 链路 5 节点速查表

| 标记 | 位置 | 正常输出 | 异常含义 |
|------|------|---------|---------|
| EARLY | apply() 开头 | `apply function STARTED` | 无此行 = 插件未加载（查 cordis 配置） |
| NODE-1 | Hook 订阅 | `Hook subscription SUCCESS (unsubscribe=function)` | FAILED = `ctx.on` 未注册成功 |
| NODE-2 | user/message 到达 | `user/message event ARRIVED (windowKey=...)` | 无此行 = 事件未派发（或消息没真发出去——查 sessions 目录是否有写入） |
| NODE-3 | pendingCapture 填充 | `pendingCapture SET (size=N, text.length=M)` | 无此行 = 窗口 bound / 消息被清洗为空 / 非 direct-human |
| NODE-4 | systemPrompt 组装 | `systemPrompt assemble (windowKey=..., pending=EXISTS/NONE)` | windowKey=undefined = 上下文提取失败 |
| NODE-5 | 提示词生成 | `DYNAMIC PROMPT (text.length≈1179)` / `STATIC GUIDANCE (620)` / `'' (reason=...)` | 返回空串看 reason：windowBound / windowKey=undefined |

## 常见误判

1. **"日志没有 = 代码没跑"是错的**：先确认你看的日志通道本身可靠（见第一原则）。REQ-f6307c 曾因此误诊"apply() 未执行"，实际链路完全正常。
2. **pending 长时间不清除不是 bug**：pending 在 turn/end 才清除；弹框等待作答、Agent 长回合期间 pending 存活属设计内（回合内持续 nag 提醒）。回合结束后看 NODE-4 的 size 是否回落 0。
3. **"弹框没弹"先排除消息没发出去**：重启前打开的浏览器标签页 WebSocket 可能已断，页面看着正常但消息发不出。判据：`find .dsh-data/sessions -mmin -5` 应有新写入；发消息后窗口应有"转圈"动画。
4. **investor-session（定时任务会话）只出现 STATIC GUIDANCE 属正常**：系统注入消息经清洗后不计入捕获。

## 验证脚本（可复核）

```bash
cd agent-dh/packages/pages/dsh-pmboard
node --import tsx/esm scripts/verify-capture-chain.mts   # 集成链路（真实 ledger）
node --import tsx/esm scripts/verify-t4-rounds.mts      # 连续 3 轮 + turn/end 清除
```

两者都应输出 PASS。失败时对照上方 5 节点表定位。

---

## 点"不立项"没生效、弹框又弹出来了（REQ-260922012924-2e29 / FR-5，2026-09-22 起修复）

**症状**：capture 弹框点"✖️ 不需要立项"后，弹框再次弹出，需求最终被创建推进。

**根因**：capture 调用方超时/中断后弹框未收回（僵尸框），用户的拒绝答复随死掉的调用静默丢失；agent 不知已拒绝而重弹。

**修复后的行为**：拒绝会落盘留痕到 `state/capture-rejections.json`（窗口+时间戳，ring buffer 50 条）；
同窗口 30 分钟内再触发 reqboard_capture → 不弹框，直接返回"用户已于 HH:MM 选择不立项"。

**排查**：`cat .dsh-data/state/capture-rejections.json` 看拒绝留痕；30 分钟后粘滞自然过期可重新立项。
注意僵尸框本身（调用方死亡后弹框未收回）属 DSH 框架 userQuestions 层，pmboard 只能保证行为正确，不能收回旧框。

## 看板/会话进度打不开需求文档（REQ-260922012924-2e29 / FR-4，2026-09-22 起修复）

**症状**：点产物/文档链接没反应或打不开，尤其是工作区非 agent-dh 的会话（如 packages/web/dsh-pmboard 下开的窗口）。

**根因**：文档路径按"当前会话工作区"解析（`dsh-resource://file/session/<sid>/docs/...`），
会话按工作区分组，dsh-pmboard 工作区下没有 docs/requirements/。

**修复后的行为**：state 端点暴露 `workspaceRoot`（= 服务端进程 cwd = agent-dh）与 `homeDir`；
客户端打开与显示一律拼绝对路径，任何工作区会话均可打开；产物按钮悬停可见 ~ 缩写绝对路径；
立项回执 note 直接打印绝对路径。旧服务端无 workspaceRoot 字段时降级为相对解析（不报错）。

## 立项四问选了非默认文档位置，需求文档路径对不上（FR-2）

Q4 选 docs/rfcs/ 等非默认位置时，路径推导（H2 输入包、阶段详情文档链接）现在消费 `docBasePath`：
含 `<REQ>` 占位符则替换为需求 id；无占位符自动追加 `<id>/` 子目录防碰撞；缺省与默认一致。

## 立项/阶段确认后上下文会不会被压缩（FR-3）

2026-09-22 起 `nodeIsolation: true`（config/cordis.yml 模板，活动配置继承）。行为：
G0 立项门在 requirement.md 未落盘时 skip(doc_not_ready) 不压（保护立项上下文）；
后续阶段门（文档已落盘）在轮次边界真压缩并留痕 `state/node-isolation-log.json`。
回滚：配置改回 false + 重启（30 秒可逆）。

## triage 兼容层已删除（2026-09-24，REQ-260922182505-0924）

以下现象**不是 bug，是预期行为**（旧 M2 流程的兼容层已全删）：

- `GET/POST /dashboard/api/reqboard/triage*` 四个端点返回 404 `not_found`；
- 看板没有"待归类"面板（buildTriage / fetchTriage / triage CSS 已删）；
- `reqboard_status` 不再返回 `has_pending` / `pending_triage_id` 字段；
- 拒绝码 `REQBOARD_PENDING_TRIAGE` 不再可能出现；
- 捕获引导只查"窗口是否 bound"，不再查遗留 pending 建议卡。

台账 `triages` 字段与 `TriageRecord` 类型**冻结保留只读**（存量 2 条 resolved 记录
照常加载，migration v4 fixture 测试是锁定证据）；`isWindowBound` 的 triage 锚点
判定保留（历史 confirmed 记录仍是窗口→需求绑定的数据锚点）。

防回归：机制退役时删除清单 = 实现本体 + 路由/面板兼容层 + 前置检查判定，
三类一起列；排查"某检查为什么永不触发"时先查它检查的对象还在不在生产。
