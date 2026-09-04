# RFC 012 P2：agent-dh evolution 工具迁移 qv2 引擎（真实回测数据源）

> 日期：2026-09-05
> 作者：investor（w-8366e526）
> 关联：docs/rfcs/012-strategy-evolution-engine.md（§10 落位记录）；P1 work-log：rfc012-p1-qv2-evolution-engine.md
> commit：edd663f0（feat(evolution): RFC 012 P2 工具层迁移 qv2 引擎）

## 背景

RFC 012 P0 已拦截 Agent OS 占位 fitness（0.05×i 阶梯冒充），P1 已在 qv2（:5001）落位策略进化引擎（真实变异 → 回测 → fitness → 落库）。P2 目标：**agent-dh evolution_* 工具从 Agent OS（:8080，占位源）切换到 qv2 引擎（真实源）**，让 agent 调 evolution_run / evolution_leaderboard 拿到的都是真实回测数字。

## 改动清单

| 层 | 文件 | 内容 |
|---|---|---|
| client | `quantsys-v2-client/src/types.ts` | +EvolutionEngineRunRequest / RunResult / RunRow / RunsResponse / Proposal 类型（camelCase 对齐引擎契约） |
| client | `quantsys-v2-client/src/client.ts` | +`evolutionRunStrategy(request)`（POST /api/evolution/engine/run）、+`getStrategyEvolutionRuns(strategyId, limit)`（GET /api/evolution/engine/runs） |
| 插件 | `agent-dh/packages/evolution/package.json` | 依赖 agent-os-client → quantsys-v2-client（workspace:*） |
| 插件 | `agent-dh/packages/evolution/src/index.ts` | Config 切 `quantsysV2`（baseURL 5001, timeout 120s）；构造 QuantsysV2Client；agentOS 配置/Client 全移除 |
| 工具 | `EvolutionRunTool/*`（v2.0.0） | 参数：strategy_id+symbol 必填、start_date/end_date 缺省自动 365 天窗口、initial_cash；mode 枚举去 validate；execute 映射 camelCase 请求、归一 snake_case 输出；data_source='qv2_real'\|'degraded'；timeout 60s→180s（full 15 变体实测 ~20s，留余量） |
| 工具 | `EvolutionLeaderboardTool/*`（v2.0.0） | 语义升级：按 strategy_id 查真实进化历史（每 run 最优变体行，fitness 降序）；三态诚实：qv2_real / degraded（全批失败）/ empty（无记录）；strategy_id 必填 |
| 测试 | `tests/evolution-qv2-contract.test.ts` | 新契约测试 8 例（mock qv2 camelCase 真实响应 → 校验 snake 归一、degraded/empty/degraded 混排、参数校验、mode 去 validate） |
| 测试 | `tests/evolution-placeholder.test.ts`（删除） | A 链占位检测测试随 placeholder.ts 退役换代 |
| 其他 | `agent-dh/vitest.config.ts` | alias 相对化（__dirname → ../quantsys-v2-client/src），main 与 git worktree 双环境可用 |
| 其他 | `agent-dh/packages/evolution/src/placeholder.ts`（删除） | A 链占位过渡物退役 |
| profile | `~/.dsh/profiles/investment/cordis.patch.yml` | evolution 插件配置 agentOS → quantsysV2（baseURL http://localhost:5001） |

## 验证证据

- `npx vitest run tests/evolution-qv2-contract.test.ts`：8/8 通过（含 qv2 camelCase → snake_case 归一、proposals.estimated_fitness 键归一、整批 degraded → 诚实降级透传原因、fitness 混排时降级行保留标注且不参与 avg、empty 空态）
- `npx vitest run tests/plugin-schema.smoke.test.ts`：19/19 通过（schema 铁律门禁）
- 运行时验证：profile 重启后 Live 调用 evolution_run/leaderboard 返回 data_source=qv2_real（见 P2-6 记录，若已执行）

## 落位差异（vs RFC §5 设计，裁决全文见 RFC 012 §10）

1. **无 aos fallback**——§5 预期 qv2 404 时保留 aos；实施取消（aos 只剩占位语义，fallback = 占位复辟后门）。
2. **leaderboard 语义升级**——跨策略占位榜 → 按 strategy_id 的真实进化轨迹排行（不同策略窗口/标的 fitness 不可比；引擎无跨策略全量榜）。
3. **data_source 命名 qv2_real**（§5 预写 qv2_real_backtest）。
4. **RunTool 参数收紧**（引擎须指定标的+窗口）；mode 去 validate（路由仅收 full/propose）。
5. **client 两方法**（§5 预写三方法；getStrategyLeaderboard 无独立后端语义）。
6. **placeholder.ts + P0 测试退役删除**（A 链数据源移除后占位检测成为死代码）。

## 待办（P3 收尾，独立于本 work-log 推进）

- B 链账户行为 fitness 盘后续采接入（对象=账户行为，分域独立，8/14 断点恢复）
- RFC 005 引用已刷新（本分支）；008 无 A 链数据源引用（line 170 指 reward 占位，另一码事）
- 观察 evolution_leaderboard Live 在真实策略（635）上返回进化历史，确认 agent 决策链路（R-001 类流程）引用真实数字
