# 测试策略 · REQ-261019224003-0041

> serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
> 判据表与 02-options §A 的 P1–P6 逐条对齐；全部在 dsh-pmboard 仓根执行。

## 1. 配置/构建门（P1–P5）（serves: FR-1, FR-2, FR-3, FR-4）

| # | 改动点 | 判定命令 | 期望读数 |
|---|---|---|---|
| T1 | boundary 清单 | `pnpm install && pnpm boundary:check` | 退出码 0；"找不到包目录"6 条红消失 |
| T2 | 依赖声明 | `ls -l pm/node_modules \| grep -c workprocess` | ≥4 条软链 |
| T3 | 内联构建 | `pnpm --filter dsh-pmboard build && grep -c "workprocess" pm/dist/index.mjs && grep -c 'from "workprocess' pm/dist/index.mjs` | 前者 > 0；后者 = 0（无裸说明符） |
| T4 | 装载清单 | `composeEntries` 复现（02 P4 命令）或重启宿主 | 5 条 entry、`skippedBundles` 为空；六个 `*_workstage`/`*_worktask` 工具可绑定 |
| T5 | 映射补齐 | `pnpm typecheck` | workprocess 相关 error = 0 |
| T6 | 包测试 | `pnpm vitest run workprocess/*/tests` | 四包自带测试（7+4+5+1 个 spec）全过 |

## 2. 接缝单元测试（serves: FR-5, FR-6, FR-7）

- 投影器纯函数：夹具（tasks/runs）→ 快照断言（需求 id 映射、一子卡一 workTask、`nextReady` 折进事实、需求级阶段不出现）；
- 写回适配：mock pm 用例层，断言驱动器每个写动词落在对应用例上、**零直写存储**（对 storage 的写调用计数 = 0）；
- 不一致对账：构造投影与台账不一致 ⇒ 必出告警（故障注入，不许静默）；
- 卡面字段：读写双向兼容（旧台账无字段按默认；非法 `closePolicy` 抛 `REQBOARD_INVALID_INPUT`）；
- 耐久记号：`asked.plan`/`asked.ask` 只问一次（重启进程后不再重复问）。

## 3. 退役收尾门（P6）（serves: FR-8）

| 判定命令 | 期望 |
|---|---|
| `grep -rlE "from '(pm-goal\|tool-pm-goal)" --include='*.ts' . \| grep -v node_modules \| wc -l` | 0 |
| `pnpm typecheck` | 退出码 0（现 93 条红清零） |
| `git status` 中 `goal/*` / `pm-workflow/` | 保持删除，不复活 |

## 4. 真机验收（serves: FR-5, FR-6, FR-9）

- 全 auto 流程：两阶段流程自动开工/收口，`~/.dsh/storages/workprocess.json` 出现 `closedAt`；
- 起链语义：手动 `reqboard_task_run` 一次后，驱动器自走下一拍（无人再触发）；
- 回归：需求级人工门（ask_confirm/验收单）全程无 workprocess 参与；
- KB 门：可解析状态下 `pnpm kb:check` 退出码 0。

## 5. 故障注入纪律（serves: FR-9）

- 装载清单：故意改错一条 insert 的 id ⇒ T4 必须失败（验证门能抓住"静默不装"）；
- 投影对账：UC-3 反向夹具 ⇒ 告警必出；
- 依据本仓教训："只测成功路径等于没测"——每道门配一条反向用例。
