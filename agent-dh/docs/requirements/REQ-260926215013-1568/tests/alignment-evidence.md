# 测试证据 · Dive 对齐 DSH Goal driver

**需求**: REQ-260926215013-1568
**采集日期**: 2026-09-26
**采集环境**: agent-dh（工作区根），包 packages/web/dsh-pmboard，DSH 0.1.6-alpha.2

## 验收命令输出

| 命令 | 结果 |
|------|------|
| `npx vitest run ./tests/dive-manager-alignment.test.ts` | **1 file passed / 11 tests passed / 0 failed**（TC-01…TC-11 ↔ FR-1…FR-11） |
| `npx vitest run ./tests/capture-hook.test.ts ./tests/dive-session-driver-wiring.test.ts ./tests/isolate-node-context.test.ts` | **3 files passed / 63 tests passed / 0 failed**（回归，需求指定） |
| `npx vitest run ./tests/dive-round-state.test.ts` | 1 file passed / 12 tests passed（T-1 契约） |
| `npx vitest run ./tests/dive-round-driver.test.ts` | 1 file passed / 11 tests passed（T-2 状态机） |
| `npx vitest run ./tests/agent-deliverer.test.ts` | 1 file passed / 9 tests passed（T-3 投递，含 2 条新增） |
| `npx vitest run ./tests/dive-manager-wiring.test.ts` | 1 file passed / 6 tests passed（T-5 七路接线） |
| `npx vitest run ./tests/t7-legacy-tolerance.test.ts` | 1 file passed / 3 tests passed（T-7 旧数据容错） |
| `npx tsc --noEmit -p tsconfig.json \| grep -c "error TS"` | **140**（改动前基线 145 → 净减 5，不高于基线） |
| `python3 scripts/relink-profile.py --check` | 退出码 **0**（5 个安装条目均符号链接、无副本漂移） |
| `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts`（工作区根） | 21 tests passed（插件构造 + 全部工具 schema 合法） |
| `grep -c followup src/application/dive/ReqboardDiveManager.ts` | **0**（续跑不再由状态事件直投） |

## 发版与线上健康

| 项 | 结果 |
|----|------|
| 构建 | `cd packages/web/dsh-pmboard && pnpm build` 退出码 0；dist/index.mjs 2026-09-26 22:48 |
| 加载 | `quick_restart` 后进程在跑：PID 13808（22:48:25 启动） |
| 看板 API | `POST /dashboard/api/reqboard/req/move` 正常返回 JSON 信封（100% 到达处理器） |
| 根路径 | `curl -o /dev/null -w '%{http_code}' http://127.0.0.1:13080/` → **401**（该端口 / 由 token 网关保护；本仓健康检查同样按 401 判 ok）。**验收单里写的 200 在本 profile 不成立，如实报出。** |

## 任务覆盖标注（covers · 供覆盖度门禁）

| 测试文件 / 命令 | covers |
|-----------------|--------|
| packages/web/dsh-pmboard/tests/dive-round-state.test.ts | covers: t-aa2ec9 |
| packages/web/dsh-pmboard/tests/dive-round-driver.test.ts | covers: t-0ddfb1 |
| packages/web/dsh-pmboard/tests/agent-deliverer.test.ts | covers: t-4a74c8 |
| packages/web/dsh-pmboard/tests/capture-hook.test.ts + packages/web/dsh-pmboard/tests/dive-session-driver-wiring.test.ts + packages/web/dsh-pmboard/tests/isolate-node-context.test.ts（T-4 组合与向后兼容回归） | covers: t-cab4a2 |
| packages/web/dsh-pmboard/tests/dive-manager-wiring.test.ts | covers: t-1aa789 |
| packages/web/dsh-pmboard/tests/dive-manager-alignment.test.ts（TC-01…TC-11 ↔ FR-1…FR-11） | covers: t-620dc0 |
| packages/web/dsh-pmboard/tests/t7-legacy-tolerance.test.ts + scripts/relink-profile.py --check + tsc 基线 | covers: t-2b3e57 |

## 种子数据与假端口

对齐单测使用 fake 端口（内存台账 / 可切 status 的假 agent / 可编排的 checkpoint promise / 记录型 logger），
不触真实 DSH 事件循环；真实宿主行为由 `plugin-schema.smoke.test.ts`（构造全部插件与工具）与重启后的线上探针覆盖。
