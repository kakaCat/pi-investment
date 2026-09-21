# REQ-9494f9 验证记录

- 状态：**部分完成 · 尚未交棒验收**。AC-1 / AC-2 / AC-3 / AC-4 / AC-6 已通过（**AC-6 判据经 2026-09-21 用户裁决修订为折叠投影判据**，见 §六）；**AC-5 待重启后核验**（用户裁决「只写修正帧，暂不重启」）。
- 窗口：w-f8006463（investor）｜需求：docs/requirements/REQ-9494f9/requirement.md ｜计划：plan.md
- 更新时点：2026-09-21 03:0x CST（数据时点见各节标注）

## 一、验收对照表

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| AC-1 | buildNudgeMessage 返回对象信封（id/role/content/source） | ✅ 通过 | §二 |
| AC-2 | 回归测试全绿，且修复前为红 | ✅ 通过 | §三 |
| AC-3 | 全仓 followup( 调用方无字符串实参 | ✅ 通过 | §四 |
| AC-4 | 折叠 inbox 投影后 next-turn 为空（不含字符串） | ✅ 通过 | §五 |
| AC-5 | 浏览器刷新 :13080 控制台无 control stream failed | ⏳ 待重启（用户裁决暂缓） | §七 |
| AC-6 | 折叠投影里字符串条目数 = 0（原文 raw grep 判据不可成立，经 2026-09-21 裁决改写） | ✅ 通过 | §六 |

## 二、AC-1 证据（t-90d985）

```bash
cd /Users/yunpeng/pi-investment/agent-dh && npx tsx -e "import {buildNudgeMessage} from './packages/solve-kit/src/host.ts'; const m:any=buildNudgeMessage({eventId:'x',title:'t',attempt:1,total:3,actorWindow:'w-a',panel:'执行看板',plugin:'dashboard-execution'}); console.log(typeof m.id, m.role, m.source.kind, m.content[0].type)"
# 输出：string user plugin text
```

改动：packages/solve-kit/src/host.ts —— buildNudgeMessage 返回 {id: randomUUID(), role:'user', content:[{type:'text',text}], source:{kind:'plugin',plugin}}，与同文件 buildSolveMessage 逐字段同形；调用点 host.ts:147 传 plugin: opts.plugin；导出该纯函数供测试。无顺手重构。

## 三、AC-2 证据（t-673e77）

```bash
cd /Users/yunpeng/pi-investment/agent-dh && npx vitest run packages/solve-kit/tests/nudge-message.test.ts
# 2026-09-21 02:53 CST 复跑：Test Files 1 passed (1)｜Tests 4 passed (4)
```

用例：A1 形状（对象 + id 为 UUID + role + content + source.kind='plugin' 且 plugin 透传）；A2 连续两次调用 id 不相等；A3 严格双重身（复刻框架两个真实读取点：inbox.mutate 读 message.id、queueItemsFromInbox 读 message.source.kind）不抛错；A4 反例锁（同一双重身对字符串必须抛错，防 A3 退化成恒真）。

**故障注入复核（失败 → 通过对比）**：把 buildNudgeMessage 临时改回 `return text`（旧行为）→ 同命令输出
```
AssertionError: expected 'string' to be 'object'
TypeError: inbox 拒绝非消息对象：message.id=undefined
 Test Files  1 failed (1)｜     Tests  3 failed | 1 passed (4)
```
还原后重跑 → 4 passed。

**未引入回归**：solve-kit + execution/solve-predispatch-guard + dsh-pmboard/agent-deliverer 共 16 tests 全绿；全量套件失败文件全部与本需求无关（既有环境问题）。

## 四、AC-3 证据（t-0f54a6 · 全仓投递形状审计）

```bash
cd /Users/yunpeng/pi-investment/agent-dh && grep -rn "followup(" packages/*/src packages/*/*/src --include=*.ts | grep -v "\.d\.ts"
```

| 调用点 | 实参 | 判定 |
|---|---|---|
| lifecycle/src/index.ts:287,372,658,848,1003,1041 | createUserMessage({...}) | ✅ 信封 |
| solve-kit/src/target.ts:35 | message（由调用方构造的信封） | ✅ 信封 |
| solve-kit/src/host.ts:147 | buildNudgeMessage({...}) | ✅ 信封（本次修复点） |
| dsh-pmboard/src/adapters/AgentDeliverer.ts | 结构复刻信封（{id,role,content,source}） | ✅ 信封 |
| dsh-pmboard/src/index.ts:270 | 注释，非调用 | —— |

结论：**无任何调用点传字符串**；"一份信封、一份字符串"的双形状已消除。

## 五、AC-4 证据（t-f0dcf2 · 存量脏数据修复）

**修复对象**：`.dsh-data/sessions/--Users-yunpeng-pi-investment-agent-dh--/session-6faac762-d721-4942-ae9a-f6463ab7cf79/session.v3.jsonl.zstd`

**备份（修复前，两次独立备份，sha256 一致）**：
```
4c0f080f…6954a  session.v3.jsonl.zstd.bak-req9494f9-20260920184930            (2421811 B)
4c0f080f…6954a  session.v3.jsonl.zstd.bak-req9494f9-before-apply-20260921025617 (2421811 B)
```

**修复动作**（2026-09-21 02:56 CST）：
```bash
node scripts/req9494f9-repair-inbox.mjs --file <上述文件> --apply
# appended: [{ target: 'next-turn', start: 0, seq: 1482 }]
# verify:   { residualBad: {}, lastSeq: 1482 }
# EXIT=0
```
写后文件 2421955 B（较修复前 +144 B，即一帧）；sha256 `0362aff0…ba116`。

**独立复核（与修复脚本不同实现，直接折叠 agent/inbox/spliced）**：
```json
{ "events": 1483, "maxSeq": 1482, "nextTurnCount": 0, "nextStepCount": 0,
  "foldedStringEntries": 0,
  "rawFramesWithStringInserted": [ { "seq": 1471, "target": "next-turn",
    "insertedPreview": "⏰ 收单催办（执行看板 · 第 1/3 次，来自 w-6faac762 的派单）…" } ] }
```

**复跑 dry-run（幂等确认）**：报告 `pending.next-turn=0`、`bad={}`、`action="无需修复"`。

**结论**：折叠投影里已无该字符串条目（next-turn 为空）→ **AC-4 通过**。★ 与 plan §5 的偏差：plan 要求"先停后改"，本轮按用户裁决未停机，改为在线追加。依据：持久化写路径为**追加式**（dsh-session-persistence-jsonl `appendLines` 以 `open(path,"a")` 写帧 + fsync，仅在写失败时 truncate 回滚）；实测该文件无进程持有的 fd（`lsof` 空）；目标 session 自 21:34 `turn/end` 起空闲，无并发写入者。故在线追加的 seq/锁竞争风险可忽略。

## 六、AC-6 —— 原文判据不成立（判据缺陷）→ **2026-09-21 用户裁决改写为折叠投影判据**

**原文判据**：`全量扫 session 日志 inserted":[" 命中 0`。**实测修复后仍命中 1**——这不是修复没生效，而是判据本身在"追加式日志"上不可能成立：

- session event log 是**可拼接帧容器**，修复帧（`removedCount:1, inserted:[]`）只把坏条目从**折叠投影**里取消，**不抹历史字节**；
- 那条原始脏帧（seq=1471）作为历史仍留在文件里，raw grep 必然命中；
- 要让它归零只能改写历史/裁剪日志——而这被需求 §7 边界明确禁止（"不改历史事件、不裁剪日志、不做迁移"）。plan §5 第 4 步"且全量扫描 hits=0"是未经实测的假设，与同一份计划的修复方式互相矛盾。

**运行时真正读的是折叠投影**（session-controller 建基线即重放 `agent/inbox/spliced`），因此正确的判据是折叠投影。用新增的全量体检脚本复核：

```bash
cd /Users/yunpeng/pi-investment/agent-dh && node scripts/req9494f9-scan-inbox.mjs; echo "EXIT=$?"
# { "scanned": 316, "sessionsWithFoldedStringEntries": 0, "bad": [], "readErrors": [],
#   "rawStringFramesStillOnDisk": 1 }
# EXIT=0
```

**结论**：316 个 session 的**折叠投影**中字符串条目数 = 0（修复前该 session 为 1）→ 等价判据通过。残留的 1 处是历史字节，非运行时故障。**改写已获裁决（2026-09-21，用户选「认可改写」）**：AC-6 定为"全量扫描各 session 的折叠 inbox 投影，字符串条目数 = 0"，执行入口 `scripts/req9494f9-scan-inbox.mjs`。任务卡 t-f0dcf2 的验收口径已同步修订（REQ-d3e61a T-9 修订通道），需求原文 §9 保留为历史记录并在此标注同步项。

## 七、AC-5 / 剩余步骤（用户裁决「只写修正帧，暂不重启」）

本轮**未重启**，故：
- 当前进程（pid 33627，启动于 2026-09-20 21:11）仍加载**修复前**的 solve-kit 代码 → 新的催办仍可能产出字符串、继续污染；
- 该进程内存中的 control stream 基线仍含那条坏消息 → **浏览器控制台报错仍然存在**（脏数据已从持久化投影消除，重启后即消失）。

**剩余动作（择时执行，已封装）**：
```bash
# 注意：需由"进程外"执行者跑（重启会中断发起会话）
python3 -c "import subprocess as s; s.Popen(['/bin/bash','scripts/req9494f9-restart-and-repair.sh'], start_new_session=True, cwd='/Users/yunpeng/pi-investment/agent-dh', stdout=open('/dev/null','w'), stderr=open('/dev/null','w'))"
# 脚本内部：stop.sh → 等端口释放 → 备份 → --apply（幂等，已修复则跳过）→ start.sh → 健康检查 → 复验扫描
# 日志：.dsh-data/state/req9494f9-repair.log
```
重启后 AC-5 由人在浏览器确认（任意窗口刷新 :13080，控制台无 `[session-controller] control stream failed`）。

**为什么不用 self_restart**：它重启前把**整个 agent-dh/ 未提交改动**提交到 agent-self/* wip 分支（packages/lifecycle/src/restart-planner.ts:111 `createWipBranch('agent-self', ['agent-dh/'], …)`）。本仓此刻有多个窗口的未提交改动（dsh-pmboard 等），回到干线时这些改动会从磁盘消失（2026-09-10 已发生同类静默抹除事故）。故改用**不含任何 git 命令**的 stop/start 编排（`scripts/req9494f9-restart-and-repair.sh`）。

## 八、回滚

```bash
# 任一环节失败，用备份覆盖目标 session 文件后重启即可回到"报错但可诊断"的原状
cp -p "<session>.bak-req9494f9-before-apply-20260921025617" "<session>"
```

## 九、本轮改动/新增文件

| 文件 | 说明 |
|---|---|
| `packages/solve-kit/src/host.ts` | 修复点：buildNudgeMessage 返回信封 + 调用点传 plugin（t-90d985） |
| `packages/solve-kit/tests/nudge-message.test.ts` | 形状/唯一性/严格双重身/反例锁 4 用例（t-673e77） |
| `scripts/req9494f9-repair-inbox.mjs` | 一次性修复脚本（默认 dry-run；—apply 写帧并回读校验） |
| `scripts/req9494f9-restart-and-repair.sh` | 一次性"停机→修复→启动→复核"编排（无 git 命令） |
| `scripts/req9494f9-scan-inbox.mjs` | 全量折叠投影体检（AC-6 的正确判据） |
| `docs/requirements/REQ-9494f9/verification.md` | 本文件 |
