# 重启防丢 Session 操作手册（Restart Session Safety Runbook）

> 版本：2026-08-31（基于 :13080 实例 PID 30345、DSH 源码与实测证据）
> 适用范围：Agent-DH / DSH Profile（13080 主服务 + 3080 dsh web）
> 核心诉求：**重启（含 self_restart 与手动重启）后会话历史不丢**。

---

## 0. 结论速览（TL;DR）

| 问题 | 状态 |
|---|---|
| self_restart 工具"做到没" | ⚠️ **不完整**：只写 pending + 退出进程，**没有拉起重启器**（源码 TODO）。依赖外部监管（用户终端 / restart-with-build.sh）拉起新进程。 |
| 重启丢 session 根因 | ✅ **已找到**：插件注入的 instruction-hint user/message 缺 \`id\` → 重启冷加载时 DSH 校验失败 → 会话打不开。 |
| 磁盘补丁 | ✅ 两份 preset 副本都已修好（\`~/.dsh-agent-dh/...\` 08-31 00:58、\`~/.dsh/...\` 08-25） |
| 当前运行进程 | ⚠️ 仍是旧代码（00:40 启动），**仍在写坏事件**（实测最新 seq 117825）→ **必须重启一次让补丁生效** |
| 落盘坏事件 | ⚠️ d8c936df 5 个 + a1484624 2 个，重启前必须修复（否则冷加载仍失败） |

---

## 1. 根因与证据链

### 1.1 现象
调用重启后，新窗口/刷新后会话历史消失；GUI 报错：
\`\`\`
SessionPersistenceCorruptionError: stored session "session-xxx" failed validation:
session event at seq XXX lacks an identified message
\`\`\`

### 1.2 根因
- 每次会话首个 user/message 会注入系统提示文件路径的 **instruction-hint**（tool-bootstrap.mjs 的 \`buildInstructionHint\`）。
- **旧版代码**构造该消息时**没有 \`id\` 字段**；而 DSH 磁盘加载校验要求 \`user/message\` 必须有 \`data.id\`（assistant/message、tool/result 须有 \`data.message.id\`）。
- 坏事件写入 session.jsonl.zstd → 进程内可正常续写，但**重启冷加载读盘时校验失败** → 会话打不开 = "历史丢失"。

### 1.3 证据时间线（实测）
| 时间 | 事件 |
|---|---|
| 08-25 19:41 | \`~/.dsh/.agent-presets/liangshen/tool-bootstrap.mjs\` 首次补丁（继承原 id，否则 randomUUID，#510） |
| 08-31 00:40 | :13080 启动（PID 30345，**加载的是补丁前的 .dsh-agent-dh 副本**） |
| 08-31 00:58 | \`.dsh-agent-dh\` 副本补丁落盘（\`id: randomUUID()\`）——但运行进程不重载插件 |
| 08-31 01:10~01:22 | 运行进程**仍产生**缺 id 事件：seq 85510 / 117825（时间戳 1788110563074）→ 证明必须重启 |
| 当前 | d8c936df 5 个坏事件、a1484624 2 个坏事件在盘上待修 |

### 1.4 结论
1. 补丁已就位，但**必须重启一次**才加载到运行进程；
2. 重启前**必须修复已落盘的坏事件**，否则这两个活跃会话冷加载仍失败；
3. 修复后新事件都带 id，问题不再复发。

---

## 2. 标准操作流程（防丢 session）

### 2.1 重启前（服务停止窗口内执行）
> 前提：:13080 已停止（脚本有运行期保护，服务在跑会拒绝执行）。

\`\`\`bash
cd /Users/yunpeng/pi-investment/agent-dh

# ① 修复两个活跃会话的缺 id 事件（自动备份 + 原子替换）
python3 scripts/repair-active-sessions.py

# ②（可选）全量扫描确认无残留坏事件
python3 scripts/scan-active-sessions.py

# ③（可选）全量清理空行（勿在服务运行时跑）
python3 scripts/fix-session-blank-lines.py
\`\`\`

输出预期：\`OK fixed=5 ...\` 与 \`OK fixed=2 ...\`，并打印备份目录 \`/tmp/session-repair-active-backup-<ts>/\`。

### 2.2 重启
- 手动重启（推荐）：\`./scripts/restart-with-build.sh\`（停服务→构建客户端→start.sh 拉起→健康检查），或按用户习惯手动启动。
- **不要**在本会话窗口内调用 \`self_restart\` 代替手动重启（当前实现只退出进程，不会自动拉起）。

### 2.3 重启后验证清单
| # | 验证项 | 方法 / 预期 |
|---|---|---|
| 1 | 服务起来 | \`lsof -ti:13080\` 有新 PID；GUI 可访问 |
| 2 | 会话列表 | session.list 正常（13080 ≈ 372 条，3080 ≈ 59 条） |
| 3 | 本窗口历史 | session.history(d8c936df) 可加载（≈7500+ 事件） |
| 4 | 另一窗口历史 | session.history(a1484624) 可加载 |
| 5 | 补丁生效 | 新产生的 instruction-hint 事件**带 id**（用 scan-active-sessions.py 复查为 0） |
| 6 | 旧窗口抽查 | 此前修复的 28+8 个文件 history 可加载 |

---

## 3. 故障回滚

- 修复前自动备份：\`/tmp/session-repair-active-backup-<ts>/{session-id}.zstd\`（**/tmp 可能被系统清理，重要时复制到项目下**）。
- 回滚（服务停止时）：
\`\`\`bash
mv /tmp/session-repair-active-backup-<ts>/session-d8c936df-*.zstd \\
   ~/.dsh-agent-dh/sessions/--Users-yunpeng-pi-investment-agent-dh--/session-d8c936df-7d52-452e-b3ea-8d5eaf87d3df/session.jsonl.zstd
\`\`\`
- 重启器自身的配置回滚：\`stateDir/config-backup-auto/\`（packages/lifecycle/src/restarter/restarter.ts 的 A-5 机制）。

---

## 4. 关键文件与命令速查

| 项 | 路径 |
|---|---|
| 修复脚本（两帧格式+补 id+运行保护+原子替换） | \`scripts/repair-active-sessions.py\` |
| 扫描脚本（找缺 id 事件） | \`scripts/scan-active-sessions.py\` |
| 空行清理脚本 | \`scripts/fix-session-blank-lines.py\` |
| 插件补丁（生效副本） | \`~/.dsh-agent-dh/.agent-presets/liangshen/tool-bootstrap.mjs\`（00:58，\`id: randomUUID()\`） |
| 插件补丁（完整版，#510 注释） | \`~/.dsh/.agent-presets/liangshen/tool-bootstrap.mjs\`（08-25） |
| self_restart 工具源码（55 行） | \`packages/lifecycle/src/tools/SelfRestartTool/SelfRestartTool.ts\` |
| scheduleRestart 完整实现（限流→锁→wip 检查点→pending(含上次消息)→spawn 包内重启器） | \`packages/lifecycle/src/index.ts\`（scheduleRestart 方法） |
| 包内独立重启器（self_restart 实际调用，node 内置依赖） | \`packages/lifecycle/dist/restarter/restarter.mjs\`（源：\`src/restarter/restarter.ts\`） |
| 旧独立重启器（已弃用，仅存档） | \`scripts/self-restart.ts\` |
| 手动重启脚本 | \`scripts/restart-with-build.sh\` |
| 会话存储 | \`~/.dsh-agent-dh/sessions/--Users-yunpeng-pi-investment-agent-dh--/{sid}/session.jsonl.zstd\` |
| 旧存储 | \`~/.dsh/sessions\`（8 个文件已修复） |

---

## 5. DSH 会话文件格式要点（未来排查必读）

- 文件 = **多帧 zstd**：帧1 = header 行（meta JSON）**单独压缩**（解压后必须恰好一行）；后续帧 = 事件批次。
- 文件末尾恰一个 \`\n\`；**不允许空行**（空行被 scanner 判为 torn record）。
- 事件 shape（**type 在顶层**）：\`{"type":"user/message","seq":N,"time":...,"data":{...},"surfaceOp":"append"}\`
  - user/message → 校验 \`data.id\`
  - assistant/message / tool/result → 校验 \`data.message.id\`
- 典型报错：
  - \`corrupt Zstandard session log: first frame is not exactly one header line\` → 单帧压缩（旧修复工具的通病）
  - \`complete frame contains a torn JSONL record\` → 文件中有空行
  - \`lacks an identified message\` → 事件缺 id
- 压缩工具：macOS 用 \`/Users/yunpeng/anaconda3/bin/zstd\`（CLI 支持多帧；python zstandard 0.23.0 无 read_frames）。

---

## 6. 旧文档勘误（重要）

| 旧文档 | 问题 |
|---|---|
| \`SESSION-REPAIR-README.md\` + \`session-repair.mjs\` | 用 **zlib gunzip/gzip 处理 zstd 文件**，方法错误；且只修 message.id、不了解两帧格式。已废弃，勿再使用。 |
| \`docs/self-restart-behavior.md\` | **已修复（2026-08-30）**：scheduleRestart 现在 spawn 包内重启器 \`dist/restarter/restarter.mjs\`（detached），文档描述与源码一致；重启器已收进 lifecycle 包，不再依赖 scripts/self-restart.ts。 |

---

## 7. 遗留事项 / 后续改进

1. **待办（立即）**：用户停 :13080 → 跑 \`scripts/repair-active-sessions.py\` → 重启 → 按 2.3 验证。
2. **✅ 已完成（2026-08-30）**：\`scheduleRestart\` 已完整实现（限流→互斥锁→wip 检查点→pending 持久化→spawn 包内重启器 detached 子进程），重启器收进 \`packages/lifecycle/src/restarter/restarter.ts\`（构建产物 \`dist/restarter/restarter.mjs\`），不依赖外部脚本；续跑消息按 dsh-schedule 模式注入重启前"上一次消息内容"。
3. **独立问题**：quantsys-v2 \`/api/stock/399300/klines\` 500 与本次无关，另行排查。
4. **备份持久化**：/tmp 备份建议归档到 \`~/backups/session-repair/\`。
