---
req_id: REQ-c48f99
doc: tests/final-verification
status: submitted
date: 2026-09-21
---

# REQ-c48f99 测试证据（命令 + 原始输出摘要）

## 1. 全量回归

    $ cd packages/pages/dsh-pmboard && npx vitest run
     Test Files  129 passed (129)
          Tests  1572 passed (1572)

（含新增：toolviews-contract 17 例 / toolviews-cards 34 例 / render-summaries 20 例；
消息卫生棘轮门禁同步通过——新增中文消息全部 fmt/模板字面量化）

## 2. 类型与构建门禁

    $ npx tsc --noEmit -p tsconfig.json   → 退出码 0
    $ pnpm build
    ✔ host dist/index.mjs 重建（renderSmart 命中 15 处）
    ✔ client lib/client.js 重建（250583 B）
    [verify-client] OK  bundle=250583 bytes, 关键符号齐全, styles.ts 括号配对（WRAP_SENTINEL 绿）

## 3. 线上实证（重启后）

    # 会话事件探针（python 读本会话 session.v3.jsonl.zstd，1422 事件）
    reqboard_status 渲染文本首行 = '📊 看板：1 个进行中需求（REQ-c48f99 implementing）'
    首行是中文摘要: True；含 JSON 明细（空行分隔）: True

    # bundle 探针（lib/client.js）
    9 个 key 全命中（reqboard_task_move/portfolio_trade/watch_manage/memory_write/decision_audit…）
    + tool.call.toolview 注册 + dsh-pm-tv 样式 + fallbackRow 代码

## 4. 用户目检（ask_user_question 三问答复）

- task_move 折叠行：「看到了：中文动作行，两两不同」（E1 ✅）
- reqboard_status 首行：「是，首行中文摘要」（E2 ✅）
- bash/read/edit：「一致」（E3 ✅）；旧会话重渲染未单独目检（同管线推定，降级标注）

## 5. 降级标注

- E4（真实畸形 block 的 GUI 兜底）：未遇到实战触发；逻辑层 vitest 9 例
  （畸形→null→fallbackRow）覆盖，待真实出现时复核。
