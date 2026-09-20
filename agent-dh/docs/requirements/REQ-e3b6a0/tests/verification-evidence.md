# REQ-e3b6a0 验收证据（命令 + 输出摘要）

- 采集时间：2026-09-20
- 采集窗口：w-878da638
- 运行实例：:13080（重启后 PID 87295；main 指向 src/index.ts，tsx 直载，新代码已在跑）

## 1. 门禁

| # | 命令 | 结果 |
|---|---|---|
| 1 | 在 packages/pages/dsh-pmboard 下 npx vitest run | Tests **13 failed / 1383 passed**；13 条逐项核对全部为既有他人债（见下），**本次新增失败 0** |
| 2 | npx tsc --noEmit -p tsconfig.json | 仅基线 1 条（src/tools/TaskExecuteTool/update-task-card.ts TS6133，非本需求） |
| 3 | pnpm build:client | verify-client OK，bundle=231967 bytes、关键符号齐全、模板哨兵通过 |
| 4 | npx vitest run tests/capture.test.ts | **23 passed**（含新增锁定用例） |

既有失败清单（本轮不修，属他人需求债）：

- REQ-a8d582：acceptance-archive(2)、client-view(1)、e2e-accept-override(1)、verify-override(2)
- REQ-327bdf：output-contract(2)、layer-boundary(1)、message-hygiene(1)、tools-dispatch(1)
- 基线：typecheck(1)、size-budget(1)

## 2. 根因实测证据

窗口 session-361c2879 转录（zstd -dc 读取）：

| 环节 | 证据 |
|---|---|
| 登记 | 4 条 user/message（source.kind=user） |
| 注入 | turn 2/3/4 的 system/message 含「检测到用户新输入」段 |
| 执行 | 17 次 tool/call 全为 run_code；PTC 子调用 read 28 / grep 7；reqboard_capture **0 次** |

## 3. 修复可复核命令

- grep -c "第一个工具调用必须是 reqboard_capture" packages/pages/dsh-pmboard/src/application/internal/capture-section.ts → 1
- grep -c "consumes pending capture" packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts → 1
- npx vitest run tests/capture.test.ts → 23 passed（含硬化语断言）

## 4. 待验（accepting 阶段采集）

| 编号 | 判据 | 采集方式 |
|---|---|---|
| AC-7.1 | 新会话窗口提一个工作意图 → agent **先**调 reqboard_capture 弹立项三问 | 真人开新窗口走查 |
| AC-11.2 | G1 点肯定项后不再输入任何消息即自动进 design；.dsh-data/state/prompt-injection-log.json 最后一条变化；.dsh-data/state/node-isolation-log.json 条目 +1 | 真人走查 + 文件核对 |
