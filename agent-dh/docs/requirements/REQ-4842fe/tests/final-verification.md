---
req_id: REQ-4842fe
doc: tests/final-verification
status: submitted
date: 2026-09-21
---

# REQ-4842fe 测试证据（命令 + 原始输出摘要）

## 1. 全量回归

    $ cd packages/pages/dsh-pmboard && npx vitest run
     Test Files  126 passed (126)
          Tests  1512 passed (1512)

## 2. 真实台账副本读取 + 渲染（端到端冒烟）

    $ npx tsx /tmp/render-check.mts
    {
     "ledger_copy": "/var/folders/.../ledger-copy-owKCXc/dsh-reqboard.json",
     "revision": 2185,
     "requirements": 51,
     "tasks": 234,
     "subtask_cards": 0,
     "lanes_bytes": 51024,
     "list_bytes": 19230,
     "ids": ["REQ-b02e99", "REQ-370b24", "REQ-a42aa4", "REQ-b12037"]
    }

脚本只 copyFileSync 台账到临时目录后读取渲染，**从不写真台账**；脚本全文见 verification.md §3。

## 3. 构建产物与哨兵

    $ pnpm -C packages/pages/dsh-pmboard build
    ✔ Build complete
    wrapped dsh-pmboard -> lib/client.js 223770 bytes
    [verify-client] OK  bundle=237780 bytes, 关键符号齐全, styles.ts 括号配对
    $ ls -l dist/index.mjs lib/client.js
    -rw-r--r-- 908882 Sep 21 03:10 dist/index.mjs
    -rw-r--r-- 237780 Sep 21 03:10 lib/client.js

## 4. 关键专项用例

| 用例文件 | 覆盖 | 结果 |
|---|---|---|
| packages/pages/dsh-pmboard/tests/client-subtask-view.test.ts（11 例，本需求新增） | 四态徽标 / 子卡链 / 进度口径（canceled 不计）/ 存量卡无子卡区 / 控制面按钮 | ✅ |
| packages/pages/dsh-pmboard/tests/auto-chain-approval.test.ts（4 例） | 批准计划后不调任何人工工具一路到 accepting；无「确认拆分清单」弹框 | ✅ |
| packages/pages/dsh-pmboard/tests/failure-handling.test.ts（8 例） | 子卡退回+attempt+1、autoRun=false、弹框指令壳投递、后续卡不执行、三选处置 | ✅ |
| packages/pages/dsh-pmboard/tests/concurrency-limits.test.ts + advance-chain.test.ts | ≤3 父卡、冲突两防线、幂等、熔断、恢复扫描 | ✅ |
| packages/pages/dsh-pmboard/tests/layer-boundary.test.ts | domain 无运行时依赖；工作流引擎只在 adapter | ✅ |
| tests/plugin-schema.smoke.test.ts（20 例） | 全部插件构造即编译 schema（本需求把 dsh-pmboard 补进名单） | ✅ |
| 消息/尺寸门禁（message-hygiene / size-budget） | 拼接式消息不超棘轮；宿主单文件 ≤400 行 | ✅（把并发窗口 6 行拼接改走 fmt 后收绿） |

## 5. 层边界原始证据

    $ grep -rn "ctx.workflowEngine" packages/pages/dsh-pmboard/src --include="*.ts"
    src/tools/TaskExecuteTool/TaskExecuteTool.ts:6   ← 注释
    src/adapters/WorkflowEngineRunner.ts:3           ← 注释（唯一实现体在本文件）
    src/application/ports.ts:214                     ← 注释

    $ grep -rnE "from .(node:|@deepseek-ai/)" packages/pages/dsh-pmboard/src/domain
    （空 → domain 无任何运行时依赖）

