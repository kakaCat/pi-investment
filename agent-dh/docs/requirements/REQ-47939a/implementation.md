# REQ-47939a 实施文档（implementing 阶段 · 按任务卡执行）

> 上游产物链：`requirement.md` → `plan.md` + `design/*.md`（4 份）→ `decomposition.md`（13 张卡）
> 本文件是**执行顺序与每步验证方式**，不重复设计内容；卡随人走，照卡执行不二次创作。

## 1. 执行顺序（严格按依赖 DAG）

| 批次 | 任务 | 开工前提 | 每步验证方式 |
|------|------|---------|-------------|
| B1 | t1 立层边界门禁与端口骨架 | 拆分已确认 | `npx vitest run tests/layer-boundary.test.ts` 绿 |
| B2 | t2 / t3 / t4（三块领域搬迁，可并行） | t1 绿 | 各自 `npx vitest run tests/domain` + 相关既有测试绿 |
| B3 | t5 适配器落地 | t1 绿 | `npx vitest run tests/application/repository.test.ts tests/capture-hook.test.ts` 绿 |
| B4 | t6 用例层落地 | t2,t3,t4,t5 全绿 | `npx vitest run tests/application` 绿 |
| B5 | t7 路由改薄 · t8 工具收敛 | t6 绿 | 路由三件 + `output-contract` + `plugin-schema.smoke` 绿 |
| B6 | t9 删旧文件 + 尺寸门禁 | t7,t8 绿 | **全量** `npx vitest run` 绿 + `src/host/agent-tools.ts` 不存在 |
| B7 | t10 账本 v4→v5 迁移 | t9 绿 | `--dry-run` 白名单外 diff=0 + `tests/migration.test.ts` 绿 |
| B8 | t11 客户端 view 拆分 · t12 styles 分层 | t9 绿 | 客户端三件测试绿 → `pnpm build:client` + 哨兵 |
| B9 | t13 文档演进与清理 | t10,t12 绿 | `wiki_probe.py` 无死链 |

## 2. 每张卡的标准执行流程（三工具闭环）

1. `reqboard_task_move(to=in_progress)` → 返回任务卡全文（做什么/怎么做/怎么算完），**照卡执行**；
2. 按卡的 `implementation` 改代码，跑卡里写明的验证命令；
3. `reqboard_task_report`（summary + completed + files_changed）→ 再 `reqboard_task_move(to=done)`。
   done 会被凭证门检查：必须有汇报、有真实工具动作、非 60s 连环关闭。**验证不过就不报 done。**

## 3. 四道贯穿性检查（每批次都跑）

| 检查 | 命令 | 不通过怎么办 |
|------|------|-------------|
| 全量回归 | `cd packages/pages/dsh-pmboard && npx vitest run` | 红了先判断是不是自己引入；是就修，不是就记录并保留 |
| 契约 | `npx vitest run tests/output-contract.test.ts` | 返回键未声明 → 补声明（该 bug 类已踩三次） |
| 层边界 | `npx vitest run tests/layer-boundary.test.ts` | 依赖方向违规 → 改 import，不放宽规则 |
| 构建（涉客户端时） | `pnpm build:client && node scripts/verify-client-build.mjs` | 构建失败先看是不是 dist 被打包器清空 |

## 4. 已知基线（不得误判为本次引入）

- 全量基线：**495 passed / 1 failed**（失败项 `tests/board-info-fixes.test.ts > 验收态尚未交材料：操作条不给 verify-pass`，本需求之前即存在，不归属本次工作）。
- 重启/发版：源码经符号链接被实例加载，改动需重启生效；真机验证走 `scripts/start.sh`（已配 lifecycle self_restart，成功率实测 3/3）。
- 契约门禁：`tests/output-contract.test.ts` 已含穷尽式静态扫描（工具所有响应型 return 的键必须已声明）。

## 5. 遇门用弹框（不自行拍板）

需要人拍板的两类：①范围变更（比如拆分后发现某设计不成立）；②方案取舍（比如工具收敛退回 13→11）。
一律 `reqboard_ask_confirm`（阶段/产物门）或 `ask_user_question`（信息征询），**弹框文本必须短**（题干 ≤200 字、选项 ≤40 字，正文放对话里——2026-09-17 实测长文本会把选项挤出可视区，用户"不能选择"）。

## 6. 收尾（全部任务 done 前）

汇总各任务汇报与证据 → `reqboard_verify_submit`（summary + evidence 必须是可复核的命令+输出摘要/报告路径）→ 需求自动进入 accepting → 用 `reqboard_accept_sheet` 逐项弹框验收。
