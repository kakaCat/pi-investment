# 部署生效验证 · REQ-260925110957-552d 前置欠账

> 关联需求：REQ-260925110957-552d（本文件为 brainstorming 阶段的部署证据附件）
> 验证时间：2026-09-25 11:15–11:2x（重启后一次性复核）
> 验证目的：回答「重新构建了吗 / 重启了吗」——把结论落成可复跑命令 + 原始输出，不靠对话记忆
> 背景：`dsh-pmboard` 的 `package.json` 是 `"main": "./dist/index.mjs"`，**从构建产物加载**，
> 「改 src → 重启」不生效，必须「`pnpm build` → 重启」。REQ-260924213231-b1c4 的 FR-3 正是因缺构建从未上线。

## 结论

| 步骤 | 结果 | 判定依据 |
|---|---|---|
| 补构建 | ✅ 已完成 | 两个产物 mtime 均为 11:12:57；`src` 中新于产物的文件数 = **0** |
| 重启 | ✅ 已完成 | 新进程 PID 10260 起于 **11:15:14**（晚于构建）；`quick-restart-result.json` `status=ok` @11:15:16 |
| 上线复核 | ✅ 通过 | 运行中进程对 `reqboard_confirm_receipt` 返回结构化业务错误 `REQBOARD_UNKNOWN_TICKET`（工具未注册时走不到业务校验） |

## 1. 构建新鲜度

```console
$ stat -f '%Sm  %N' -t '%Y-%m-%d %H:%M:%S' packages/web/dsh-pmboard/dist/index.mjs packages/web/dsh-pmboard/lib/client.js
2026-09-25 11:12:57  packages/web/dsh-pmboard/dist/index.mjs
2026-09-25 11:12:57  packages/web/dsh-pmboard/lib/client.js

$ find packages/web/dsh-pmboard/src -type f -newer packages/web/dsh-pmboard/dist/index.mjs | wc -l
src files newer than dist/index.mjs: 0
newest src file:
2026-09-25 02:23:54  packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts

$ grep -c reqboard_confirm_receipt packages/web/dsh-pmboard/dist/index.mjs
reqboard_confirm_receipt in dist: 12 hits
$ grep -c reqboard_note_interruption packages/web/dsh-pmboard/dist/index.mjs
reqboard_note_interruption in dist: 10 hits
$ grep -c 'PendingConfirmRegistry' packages/web/dsh-pmboard/dist/index.mjs
pendingConfirmRegistry markers: 4 hits
```

> 口径说明：仅统计 `src/` 下的源码；`lib/client.js` 是客户端**构建产物**（同一次构建 11:12:57 写出），不计入「源码新于产物」。

## 2. 重启与进程归属

```console
$ echo "pidfile=$(cat .dsh-data/state/server.pid) port=$(cat .dsh-data/state/server.port) listener=$(lsof -ti:13080 -sTCP:LISTEN)"
pidfile=10260 port=13080 listener=10260

$ ps -o pid,lstart,command -p $(cat .dsh-data/state/server.pid)
  PID STARTED                      COMMAND
10260 Fri Sep 25 11:15:14 2026     node --import tsx/esm .../node_modules/@deepseek-ai/dsh/lib/bin.js --profile ...

$ cat .dsh-data/state/quick-restart-result.json
{"status":"ok","reason":"REQ-260925110957-552d 前置：补构建后重启 …… 重启后复核工具表出现 reqboard_confirm_receipt","detail":"HTTP 401","at":"2026-09-25T11:15:16+0800"}

$ cat .dsh-data/state/quick-restart-resume.done.json
{"reason":"…","at":1790306102199,"sessions":[{"agentId":"session-c954a261-4edb-4445-b1ff-56a53a9b5431","status":"running","at":1790306102199}]}
```

时间链：**构建 11:12:57 → 重启请求 11:15:02（requestedAt=1790306102199）→ 新进程 11:15:14 → 结果 ok 11:15:16**。
消费者与生产者一致性：pidfile == 监听 :13080 的 pid == 当前进程 pid。

> 口径说明：`quick-restart-result.json` 的 `"detail":"HTTP 401"` **不是失败**——健康检查打在带鉴权的端点上，
> 服务器能应答即代表存活（同文件 `status:"ok"`）。

## 3. 上线复核（活体工具表，非日志推断）

```console
$ reqboard_confirm_receipt(ticket="pc-does-not-exist")
reqboard_confirm_receipt 未执行：ticket pc-does-not-exist 未知或已过期（不属于本窗口或超出有效期）
——回执事务已不可查，改调 reqboard_status 读 design_docs[].confirmed（以台账为准）（REQBOARD_UNKNOWN_TICKET）
```

判定逻辑：`REQBOARD_UNKNOWN_TICKET` 是**业务级**错误码，只有工具已注册、已进入 `ticket` 校验分支才可能返回；
若工具未注册（旧 dist 运行时）只会得到「未知工具」。**故 b1c4 FR-3（弹框非阻塞 + 挂起回执）确已上线。**

## 4. 复跑方式

```bash
cd agent-dh
stat -f '%Sm  %N' -t '%Y-%m-%d %H:%M:%S' packages/web/dsh-pmboard/dist/index.mjs
find packages/web/dsh-pmboard/src -type f -newer packages/web/dsh-pmboard/dist/index.mjs | wc -l   # 期望 0
ps -o pid,lstart -p $(cat .dsh-data/state/server.pid)
```

## 5. 对本需求的约束

A10 判据不变并据此收紧：**本需求交付时必须走完「`pnpm build` → 重启 → 工具表出现 `reqboard_run_status`」**，
且 `dist/index.mjs` mtime 不旧于 `src` 最新改动。**不得只改 `src` 就宣称完成。**
