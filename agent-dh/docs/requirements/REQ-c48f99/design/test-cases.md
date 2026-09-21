---
req_id: REQ-c48f99
doc: design/test-cases
serves: FR-2, FR-4, FR-5, FR-6
status: design
---

# REQ-c48f99 设计 · 测试策略

## 1. 纯函数单测（vitest，host 侧跑）  `serves: FR-2, FR-4`

覆盖 parseArgs / resultJson / 中文映射 / 9 张卡片的 summarize，每张卡四档输入：

| 档位 | 输入 | 期望 |
|---|---|---|
| 正常 | 完整 args + 完整结果 | 折叠行含中文动作词，两两不同参数产出两两不同文案 |
| 缺字段 | args 缺 to / 结果缺字段 | 降级用剩余字段，不 throw |
| 畸形 | argsRaw 为半截 JSON | parseArgs 返回 undefined → fallbackRow |
| error 态 | isError=true + 错误结果 | 红 icon + 结果首行为错误摘要 |

跑法：`cd packages/pages/dsh-pmboard && npx vitest run` 全绿。

## 2. 构建门禁  `serves: FR-1`

`pnpm build:client` 通过且 `node scripts/verify-client-build.mjs` 退出码 0
（WRAP_SENTINEL 哨兵在位——行首注入污染即构建失败）。

## 3. 端到端实测（重启 profile 后新会话）  `serves: FR-2, FR-5, FR-6`

| # | 操作 | 期望（可证伪） |
|---|---|---|
| E1 | 连续 3 次不同 to 的 reqboard_task_move | 折叠行两两不同且含中文动作词（对照审计报告改前 76 行全同） |
| E2 | 调用 reqboard_status | 展开体第一行为中文摘要（非 `{` 开头） |
| E3 | 各调一次 bash/read/edit | 显示与改前一致（终端卡/读取卡/diff 卡不变，FR-6） |
| E4 | 拦截一次失败调用（畸形 block） | 显示兜底行，会话渲染不中断（FR-4） |

## 4. 不做  `serves: FR-6`

- 不测框架层（GenericToolCard 本身属 DSH 主仓，不在本仓测试范围）；
- 不做像素级视觉回归（无该设施，E3 用人工肉眼比对）。
