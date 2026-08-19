# Agent-DH 复审审计报告

**审计日期**: 2026-08-19
**审计范围**: agent-dh 全部 19 个 workspace 包（14 个 Cordis 插件 + 3 个客户端库 + investment-agent-loop + CLI）
**审计方式**: 静态代码审计 + 真实构建/测试/类型检查 + **真实 5001/8080 后端路由交叉验证**（逐端点比对，非凭文档）
**前次审计**: [AUDIT-REPORT-2026-08-18.md](./AUDIT-REPORT-2026-08-18.md)、[STUB-ANALYSIS-REPORT.md](./STUB-ANALYSIS-REPORT.md)

---

## 一、总体结论

**上一轮审计的 P0/P1 问题已全部修复**，项目健康度显著改善：

| 上轮问题 | 状态 | 验证方式 |
|---------|------|---------|
| 25 个 client 方法缺失 | ✅ 全部实现 | 逐方法 grep + 实现检查 |
| 4 个插件依赖声明错误 | ✅ 已修复 | memory/evolution/scheduler/notification 现声明 `agent-os-client` |
| 3 个投资工具无真实 API | ✅ 已接线 | macro/north-flow/sentiment 调用真实端点（后端确认存在） |
| scheduler enable/disable/delete | ✅ 已实现 | 源码确认 |
| trading/intelligence 旧架构残留 | ✅ 已清理 | `src/tools/` 目录已删除 |
| 构建 | ✅ 通过 | `pnpm -r build` 19 包全绿 |
| 类型检查 | ✅ 通过 | `tsc --noEmit` 零错误（strict 模式） |
| 真实 5001 冒烟 | ⚠️ 8/9 | 唯一失败为 kline 数据缺失（数据问题，非契约问题） |

**但本次复审新发现 1 个线上工具 404（P0）和 2 个 client 端点路径错误（P1）**——与上轮"L1 虚构 URL"同类问题在新增代码中复发，说明缺 CI 防线。

---

## 二、🔴 新发现问题（需修复）

### P0-1：`market_style_detect` 工具线上 404（契约路径错误）

- **调用链**: `packages/market/src/index.ts:66` → `qv2.getMarketStyle()` → `packages/quantsys-v2-client/src/client.ts:337`
- **client 请求**: `GET /api/analysis/market-style`
- **后端真实路由**: `GET /api/market/style`（`quantsys-v2/adapters/inbound/fastapi_app/routes/market_style_async.py:14`）
- **实测证据**（2026-08-19，真实 5001）:
  ```
  GET /api/analysis/market-style → 404
  GET /api/market/style          → 200
  ```
- **修复**: client.ts 中路径改为 `/api/market/style`，并核对返回字段与 output schema（`primary_style`/`leading_sectors` 等）是否对齐真实响应。

### P1-1：`createPool()` 端点路径错误

- **位置**: `client.ts:246`，请求 `POST /api/pools/create`
- **后端真实路由**: `POST /api/pools`（RESTful，`adapters/inbound/api/routes/pools.py:75`）
- **影响**: 当前无插件工具调用此方法（死代码），但一旦使用即 404。

### P1-2：`listSignals()` 端点路径错误

- **位置**: `client.ts:308`，请求 `GET /api/signals/list`
- **后端真实路由**: `GET /api/signals`（FastAPI `signals_async.py:371` / Flask `signals.py:56`）
- **实测**: `/api/signals/list` → 422（命中其他路由的参数校验），`/api/signals` → 200。
- **影响**: 当前无插件工具调用（死代码）。

### P1-3：`pnpm test` 整体必挂（测试脚本配置缺陷）

- **现象**: `pnpm -r test` 在第一个包即失败退出。
- **根因**: `agent-os-client`、`quantsys-v2-client`、`agent-dh-client` 三个包声明了 `"test": "vitest run"` 但**没有任何测试文件**，vitest 找不到测试时退出码为 1，`-r` 模式遇错即停。
- **现状**: 全仓库仅 `investment-agent-loop` 有测试（16 个用例，全部通过 ✅）。
- **修复**: 三选一：给无测试包的 vitest 加 `passWithNoTests: true`；移除其 test 脚本；或补测试。

### P2-1：`pnpm lint` 不可用

- 根 package.json 声明 `"lint": "eslint ."`，但仓库**没有 eslint 配置文件**，直接报错退出（exit 2）。
- **修复**: 补 `.eslintrc` / `eslint.config.js`，或从 scripts 移除 lint。

### P2-2：仓库内遗留未跟踪备份目录

- `agent-dh/agent-dh.bak.1787046686/`：完整旧版备份（含 node_modules 级文件），**未被 .gitignore 排除也未被 git 跟踪**。
- **风险**: `git add .` 会误提交数百 MB 冗余；建议删除或加入 `.gitignore`。

### P3：文档漂移

| 项 | 文档声称 | 实际 |
|----|---------|------|
| README 版本 | 0.1.0 | package.json 0.1.1 |
| 工具总数 | 48（上轮审计口径） | 实际注册 47 个（14 插件逐一计数） |
| agent-dh 根目录 MD | 6 个（含 AUDIT-FIX-SUMMARY 等工作报告） | 按仓库文档规范，工作报告应入 `docs/work-logs/YYYY-MM/`，使用指南应入 `docs/` |

---

## 三、验证记录（本次实测）

### 构建 / 类型 / 单测

```
pnpm -r build     ✅ 19/19 包构建通过（tsdown/rolldown，~3s）
pnpm typecheck    ✅ tsc --noEmit 零错误（strict + noUnusedLocals 等全开）
investment-agent-loop 单测  ✅ 2 文件 16 用例全过
pnpm -r test      ❌ 必挂（见 P1-3，非代码错误）
pnpm lint         ❌ 无 eslint 配置（见 P2-1）
```

### 端点契约交叉验证（client ↔ 真实后端）

- **quantsys-v2-client**: 提取 client 全部 59 个端点，逐一与 quantsys-v2 后端（FastAPI `adapters/inbound/fastapi_app/routes/` + Flask `adapters/inbound/api/routes/`，含 blueprint prefix 重组）比对。
  - ✅ 56/59 存在；❌ 3 个错误路径（即上方 P0-1 / P1-1 / P1-2）。
  - 上轮验证过的 quote/kline/financial/pools/strategies/watch/portfolio/evolution 等端点本次复核仍然正确。
- **agent-os-client**: 提取全部 21 个 `/api/v1/*` 路径，与 agent-os（Go）`internal/api/http_server.go` 注册表比对——**全部命中** ✅（registry/scheduler/memory/evolution/notifications）。

### 真实 5001 集成冒烟（`scripts/integration-smoke.mjs`）

```
✅ data_fetch_quote      贵州茅台实时行情（tencent 源）
❌ data_fetch_kline      404 "No kline data for 600519" — DB 无数据（已知数据问题，契约正确）
✅ data_fetch_financial  财务数据（eastmoney_direct）
✅ pool_list             29 个股票池
✅ strategy_list         136 个策略（分页）
✅ watch_list            28 条盯盘规则
✅ account_info          agent_virtual 账户
✅ position_list         1 个持仓
✅ evolution_status      进化排行榜 + 决策评分
```

### 安全扫描

- 硬编码密钥/密码/token：未发现 ✅（凭证走环境变量 + dsh-credentials-local）
- `eval`/危险动态执行：未发现 ✅
- 敏感信息泄露：`QUICKSTART.md` 文件权限为 `-rw-------`（0600），含配置信息，权限合理 ✅

---

## 四、风险评级汇总

| # | 问题 | 等级 | 影响 | 建议 |
|---|------|------|------|------|
| P0-1 | market_style_detect 工具 404 | 🔴 | 线上工具必崩 | 立即改 client 路径为 `/api/market/style` |
| P1-1 | createPool 路径错误 | 🟡 | 死代码，调用即 404 | 改为 `POST /api/pools` |
| P1-2 | listSignals 路径错误 | 🟡 | 死代码，调用即异常 | 改为 `GET /api/signals` |
| P1-3 | `pnpm test` 必挂 | 🟡 | CI 无法接入 | vitest `passWithNoTests` |
| P2-1 | lint 无配置 | 🟢 | 工程规范缺失 | 补 eslint 配置 |
| P2-2 | .bak 备份目录未隔离 | 🟢 | 误提交风险 | 删除或 gitignore |
| P3 | 文档漂移 | 🟢 | 误导使用者 | 版本号/工具数/文档归位 |

---

## 五、根本性问题与防线建议

上轮审计的"L1 虚构 URL"问题在新增端点（game/ml/rotation 等 P0 方法）中**部分复发**（3/59）。虽然复发率已从 100% 降至 5%，但说明修复仍是"人工逐条核对"而非常态化验证。建议：

1. **把端点契约比对脚本化进 CI**：本次审计用的"提取 client 端点 → 比对后端路由表"方法可固化为脚本（如 `scripts/contract-check.mjs`），纳入 CI 与 `scripts/integration-smoke.mjs` 并列。
2. **扩展冒烟脚本覆盖面**：现冒烟仅覆盖 9 个工具，47 个注册工具中 38 个无真实链路验证；至少应为每个插件挑 1 个只读工具进冒烟集。
3. **修复 P1-3 后将 `pnpm test` 接入 CI**，避免"测试脚本形同虚设"。

---

## 六、结论

**Agent-DH 当前处于"主干可用、边缘有刺"状态**：构建、类型、核心交易链路（9 工具冒烟 8/9）、agent-os 客户端契约全部健康；上轮 25 方法缺口已补齐。剩余风险集中在 3 个端点路径错误（其中 1 个影响线上工具）和测试/lint 工程基础设施虚设。

**修复顺序**: P0-1（一行路径修改）→ P1-1/P1-2 → P1-3（CI 前提）→ P2/P3。

> 本报告为只读审计产出，未修改任何代码；报告文件本身未提交 git，遵循仓库 worktree 规范由人工决定是否归档提交。
