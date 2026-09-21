# REQ-9494f9 拆分计划 · 修复 solve-kit 催办把字符串当消息投递导致控制流崩溃

- requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
- 类型：bug ｜ 档位：轻档 ｜ 窗口：w-f8006463（investor）
- 需求文档：docs/requirements/REQ-9494f9/requirement.md
- 一句话目标：消除"字符串当消息投递"的形状缺陷，并清掉它留下的唯一一条持久化脏数据，使 Host 级 control stream 恢复且不再回潮。

## 1. 复现（先复现，两条最小用例）

serves: FR-1, FR-2

**R-1 · 形状复现（红）**：对**修复前**代码执行下列断言应失败——它证明催办投递物不是消息对象：

```js
const msg = /* buildNudgeMessage(...) 当前返回值 */
typeof msg === 'object' && typeof msg.id === 'string'   // 期望 true，实为 false
msg.source?.kind                                        // 期望 'plugin'，实为 undefined
```

落成可执行用例：`npx vitest run packages/solve-kit/tests/nudge-message.test.ts`（t2 新建；修复前必须红）。

**R-2 · 数据复现（已复现）**：脏数据至今仍在持久化日志中——

```bash
find .dsh-data/sessions -name 'session.v3.jsonl.zstd' | while read f; do
  zstd -d -c "$f" | grep -q 'inserted":\["' && echo "HIT $f"
done
# 实测输出：HIT .../session-6faac762-d721-4942-ae9a-f6463ab7cf79/session.v3.jsonl.zstd（scanned=315 hits=1）
```

## 2. 根因定位（判定依据）

serves: FR-1

- 缺陷点：`packages/solve-kit/src/host.ts:106-114` `buildNudgeMessage()` 返回 `[...].join(NL)` 纯字符串；`host.ts:134` 直接 `agent.followup(buildNudgeMessage({...}))`。
- 契约点：`agent.followup` 收 **UserMessage 信封**——`dsh-agent-loop/lib/index.js:789` → `inbox.splice → mutate`（:194 读 `message.id` 去重）。
- 爆点：`dsh-api-session-controller/lib/index.js:1162` `queueItemsFromInbox` 读 `message.source.kind` → TypeError；`baseline()`（:1055-1069）遍历**全部** session，故污染扩散到所有窗口。
- 判定依据：日志两行成对（`收单催办已投递` → `message "undefined" is already pending`）+ `seq=1471` 的 `inserted[0]` 为字符串 + 全量扫描唯一命中。

修复前**禁止**任何"先改了看"的动作；本节即定位结论。

## 3. 修复方案（代码，最小改动）

serves: FR-1, FR-3

只改 `packages/solve-kit/src/host.ts` 一处：

1. `buildNudgeMessage(p)` 参数增加 `plugin`，返回信封（与同文件 `buildSolveMessage` 逐字段一致）：
   ```js
   return {
     id: randomUUID(),                        // randomUUID 已在本文件 import
     role: 'user',
     content: [{ type: 'text', text: lines.join(NL) }],
     source: { kind: 'plugin', plugin: p.plugin },
   }
   ```
2. 调用点 `host.ts:134` 传 `plugin: opts.plugin`（`opts` 已有该字段，`SolveKitHostOptions.plugin`）。
3. `export` 该纯函数供测试直接断言（**仅导出，不改语义**）。

**不做**（守 bug 档"禁止顺手重构"）：不把催办改走 `deliverMessage`（信封仍须由调用方构造，改道纯属搬迁）；不加运行时形状守卫；不动计时器。

## 4. 回归测试（修复项必配）

serves: FR-2

新建 `packages/solve-kit/tests/nudge-message.test.ts`，断言：

- **A1 形状**：返回对象；`typeof id === 'string'` 且符合 UUID 形态；`role === 'user'`；`content[0].type === 'text'` 且含预期文案；`source.kind === 'plugin'` 且 `source.plugin` 透传。
- **A2 唯一性**：连续两次调用 `id` 不相等（对治 `message "undefined" is already pending`）。
- **A3 契约**：把返回值喂给一个"严格双重身"（模拟 `inbox.mutate` 的去重：要求 `id` 为字符串且唯一；模拟 `queueItemsFromInbox`：读 `message.source.kind`），不得抛错。

## 5. 存量数据修复（停实例 → 备份 → 追加修正帧 → 启动）

serves: FR-4

日志格式已核实为**可拼接的独立 zstd 帧容器**（`dsh-session-persistence-jsonl` "concatenated-frame container"；每帧 checksumFlag=1）。事件信封：`{"type","seq","time","data"}`，当前最后 `seq=1481`（`turn/end`）。

步骤（**先停后改**，避免与在线写入器的 seq/锁竞争）：

1. `./scripts/stop.sh`，确认 `:13080` 无监听、`state/server.pid` 进程已退。
2. 备份：`cp session.v3.jsonl.zstd session.v3.jsonl.zstd.bak-req9494f9-<ts>`。
3. 追加一帧（node，checksum 与后端一致）：
   ```js
   const line = JSON.stringify({ type: 'agent/inbox/spliced', seq: 1482, time: Date.now(),
     data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [], outcome: 'canceled' } }) + '\n'
   const frame = zlib.zstdCompressSync(Buffer.from(line), { params: { [zlib.constants.ZSTD_c_checksumFlag]: 1 } })
   fs.appendFileSync(file, frame)
   ```
   （`start:0/removedCount:1` 精确移除该 session `next-turn` 中唯一那条字符串；`inserted:[]` 必填。）
4. 复算校验：解压后折叠 inbox 投影 → `next-turn === []`；且全量扫描 hits=0。
5. `./scripts/start.sh` 拉起，确认 `:13080` 健康。

**丢弃内容声明**：被移除的正是那条**无法投递的坏消息本身**（w-6faac762 从未收到合法催办），无正当业务消息被删。

## 6. 线上核验与证据

serves: FR-5

- 浏览器（**任意窗口**）刷新 :13080，控制台无 `[session-controller] control stream failed`；
- 修复后实际再触发一次催办（或等价单测），日志不再出现 `already pending`；
- 证据留档：改动 diff、测试输出、扫描命令与输出、重启前后日志片段。

## 7. 留痕

serves: FR-6

`decision_audit(record)`（含 root cause + 动作 + 证据 + 数据来源时点）+ `memory_write`（经验：**跨进程契约的形状纪律**——"同包内一份信封一份字符串"必然出事；扩展名/类型系统抓不住，只有回归测试锁得住）。

## 8. 任务表

serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6

| key | 标题 | phase | depends_on |
|---|---|---|---|
| t1 | 修 buildNudgeMessage 信封并让调用点传 plugin | implement | — |
| t2 | 补催办消息形状回归测试 | test | t1 |
| t3 | 修复 session-6faac762 脏 inbox 并核验控制流恢复 | implement | t1 |
| t4 | 审计全仓投递形状并归档验证证据 | review | t2, t3 |

## 9. 边界与风险

serves: FR-1

- **边界**：不改 DSH 框架（node_modules）；不改其他投递点形状（只读审计）；不迁移/裁剪 session 历史；不加运行时守卫。
- **风险 R1**：追加帧若格式不符 → 读取器在 `scanZstdFrames` 报 corrupt 并拒绝读取该 session。缓解：帧参数与后端一致（checksumFlag=1）+ 先备份 + 追加后立即解压回读校验。
- **风险 R2**：修复期间实例停机 → GUI 短暂不可用。缓解：停机窗口最小化（三步顺序执行），完成后立即 start 并健康检查。
- **风险 R3**：`seq` 取值错（非 1482）会破坏连续性。缓解：追加前用脚本从文件读出 `max(seq)+1`，不硬编码。
- **回滚**：任一步失败 → 用备份覆盖 session 文件后 `./scripts/start.sh` 复原（回到"报错但可诊断"的现状）。
