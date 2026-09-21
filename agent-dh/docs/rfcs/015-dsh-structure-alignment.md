# RFC 015: agent-dh 目录骨架对齐 deepseek-harness

- 状态：提案（2026-09-21 用户已批准方案 1 + pages→web 改名 + 执行时机）
- 范围：**只动目录骨架**。构建体系（tsconfig/tsdown/vitest 分层）与框架钉版（rc.1 全图）均不在本期范围
- 基准：`/Volumes/ORICO/doc/github/deepseek-harness`（dsh 框架仓库）

## 背景

dsh 框架仓库的组织方式是 `apps/{cli,desktop,web}` 应用入口 + `packages/<domain>/<pkg>` 技术域两级归类
（如 `packages/web/tool-web`、`packages/session/session-format-*`）。agent-dh 当前是 23 个包平铺
`packages/*` + 页面域嵌套 `packages/pages/*`，且根目录有散落垃圾文件。

用户裁定（2026-09-21）：agent-dh 文件结构按 deepseek-harness 设计，本期只做目录骨架对齐。

## 目标布局

```
agent-dh/
├── apps/
│   └── web/                  # 已存在，不动。不重建 apps/cli（历史遗留已删，YAGNI）
├── packages/
│   ├── tools/                # host 工具插件（17 个）
│   ├── web/                  # 页面插件（7 个，自 packages/pages/ 迁入改名）
│   ├── client/               # API 客户端库（1 个）
│   ├── runtime/              # 运行时/管理包（4 个）
│   └── core/                 # 纯类型规范包（1 个）
├── config/  docs/  scripts/  tests/  ...   # 不动
└── （根目录垃圾按下方处置表清理）
```

## 包迁移映射（30 个，包名全部不变）

| 目标域 | 成员 |
|---|---|
| `packages/tools/` | competition, data-manager, evolution, evolver, factor, genome（host 插件）, intelligence, investment, learning, lifecycle, market, memory, notification, risk, scheduler, strategy, trading |
| `packages/web/` | bulletin, dsh-pmboard, execution, genome（页面插件）, holdings, page-kit, web-liveness（自 `packages/pages/` 迁入） |
| `packages/client/` | agent-dh-client |
| `packages/runtime/` | agent-os-manager, investment-agent-loop, quantsys-v2-manager, solve-kit |
| `packages/core/` | core-tool |

**关键约束：所有 package.json 的 `name` 保持原值**（`@pi-investment/trading` 等）。
跨包 import 走包名不走相对路径，因此源码、cordis.yml 插件名、pnpm workspace
依赖声明（`workspace:*`）全部零改动。`quantsys-v2-client` 在仓库顶层（`../../quantsys-v2-client`，
file: 引用），不在本期范围。

## 需要同步更新的引用点

| 位置 | 改动 |
|---|---|
| `pnpm-workspace.yaml` | `packages/*` + `packages/pages/*` → `packages/*/*` |
| root `package.json` `workspaces` 字段 | 同上（与 pnpm-workspace.yaml 保持一致） |
| `scripts/relink-profile.py` | 包名→目录映射表（已支持多层，核对新路径） |
| `scripts/restart-with-build.sh`、`scripts/req81aabd-restart-and-migrate.sh` 等 | 硬编码相对路径 |
| `scripts/req47939a-*.mjs`、`scripts/audit-tool-output-contract.mjs` | 硬编码 packages/pages 路径 |
| `tests/`（plugin-schema.smoke.test.ts、reqboard-task-execute.test.ts、m3 等） | import/断言路径 |
| `agent-dh/CLAUDE.md`、相关 docs | 项目结构章节 |
| `config/cordis.yml` | 预期零改动（按包名解析），搬迁后实测确认 |

## 根目录垃圾处置

| 文件 | 处置 |
|---|---|
| `+v).join(n))`（0 字节，shell 事故残片） | 删除 |
| `.DS_Store` | 删除（补 .gitignore） |
| `dist/`（8-19）、`output/`（8-26） | 核实无引用后删除 |
| `CLEANUP-PLAN.md`、`MIGRATION-COMPLETE.md`、`MIGRATION-DONE.md`、`index.html`、`src/`、`public/`、`.env.backup` | **不动**——均为 2026-09-21 当天时间戳，是并行会话 apps/web 迁移的在途产物，归该会话处置 |
| `cordis.yml`（根级历史参考） | 不动（CLAUDE.md 明确保留） |

## 执行方式（方案 1：一次性原子搬迁）

1. **前置条件（硬门槛）**：
   - 当前 wip 分支 `agent-self/20260921-182056`（REQ-f6307c/c48f99）合回 main
   - 并行会话的 apps/web 迁移在途工作收尾（其产物时间戳为 09-21 当天）
   - 主工作区干净、位于 main
2. 从 main 建隔离 worktree（`git worktree add .claude/worktrees/dsh-structure -b feat/dsh-structure-alignment`，建后 rebase 本地 main）
3. 全部移动走 `git mv` 保历史；同步改引用点清单
4. `pnpm install` 重建 node_modules 链接 → `python3 scripts/relink-profile.py` 恢复符号链接
5. 验证：`npx vitest run tests/plugin-schema.smoke.test.ts` 全绿 + `./scripts/start.sh` 重启 :13080 后实测工具调用
6. 合并回 main，推送

回滚：单一原子提交，`git revert` 或重置即回退。

## 风险

- **多会话撞车**：搬迁期间任何会话在旧路径上的未提交改动都会悬空——故前置条件第 2 条是硬门槛，执行当天在会话间通告
- **relink/硬链接回潮**：`pnpm install` 会把 `@pi-investment/*` 符号链接换回硬链接副本，必须紧跟 relink-profile.py（已有流程）
- **遗漏路径引用**：上表引用点清单执行时以 `grep -rn "packages/" --include='*.{ts,mjs,py,sh,yaml,yml,json}'` 全量复核为准
