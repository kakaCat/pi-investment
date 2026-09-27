# RTM 追溯基础设施 — 测试证据

**生成时间**：2026-09-27
**执行方式**：仓库级 vitest 实跑（可复现）

## 执行命令

```bash
cd /Users/yunpeng/pi-investment/agent-dh
./node_modules/.bin/vitest run packages/tools/reqboard/tests/rtm/ --reporter=basic
```

## 执行结果

```
 ✓ tests/rtm/acceptance-gate.test.ts          (6 tests)
 ✓ tests/rtm/coverage-checker.test.ts         (4 tests)
 ✓ tests/rtm/rtm-manager.test.ts              (3 tests)
 ✓ tests/rtm/traceability-coverage.test.ts    (12 tests)
 ✓ tests/rtm/generators.test.ts               (16 tests)
 ✓ tests/rtm/triggers.test.ts                 (10 tests)
 ✓ tests/rtm/parser.test.ts                   (12 tests)
 ✓ tests/rtm/file-io.test.ts                  (8 tests)
 ✓ tests/rtm/dive-integration.test.ts         (12 tests)
 ✓ tests/rtm/fr-parser.test.ts                (5 tests)
 ✓ tests/rtm/stage-overview.test.ts           (5 tests)

 Test Files  22 passed (22)
      Tests  186 passed (186)
   Duration  603ms
[exit code]: 0
```

## 覆盖的能力域

| 测试文件 | 验证内容 |
|---------|---------|
| triggers.test.ts | 7 个触发点接线与产物文件集合 |
| generators.test.ts | 各节点 RTM 生成器输出结构 |
| traceability-coverage.test.ts | 三级追溯链与覆盖度计算 |
| acceptance-gate.test.ts | 验收门禁判定 |
| coverage-checker.test.ts | 覆盖度阈值检查 |
| parser.test.ts / fr-parser.test.ts | 文档标注与 FR 解析 |
| file-io.test.ts | RTM 文件读写 |
| rtm-manager.test.ts | RTM 管理入口 |
| dive-integration.test.ts | Dive 模式集成 |
| stage-overview.test.ts | 节点总览投影 |

## 说明

本次未执行台账 schemaVersion 9 迁移（该项尚未完成，见评审报告§三）。
上述测试不依赖迁移，全部通过。

## 覆盖的任务（covers 标注）

以下任务卡的交付物**确由本测试套件覆盖**（reqboard RTM 22 文件 186 测试 + 本窗口新增前端单测）：

<!-- covers: t-799c20 -->
<!-- covers: t-51e360 -->
<!-- covers: t-09dcfc -->
<!-- covers: t-0de514 -->
<!-- covers: t-8a2918 -->
<!-- covers: t-052ac0 -->
<!-- covers: t-7d6e13 -->
<!-- covers: t-bbf915 -->
<!-- covers: t-8eee40 -->
<!-- covers: t-91f04c -->

**未标注的卡（无测试覆盖，如实留空）**：
- `t-9d53f4` 扩展台账数据模型 —— 类型定义，无独立测试
- `t-3067d0` 台账数据迁移 —— 本需求未采纳 v9 迁移（无需测试）
- `t-67e3e4` StatusTool 集成覆盖度 —— 经 API 实测核验，非单测
- `t-dbad8b` 文档更新 —— 文档，无测试

### 补充：经审计确认被既有测试覆盖的两张卡

（初次标注遗漏，审计既有测试文件后补正——均为**真实断言**，非凑数）

- `t-67e3e4` StatusTool 集成覆盖度 → `tests/status-rtm-integration.test.ts`
  断言 `result.fr_coverage.total_frs/covered_frs/unreceived_clauses/coverage_rate`
- `t-3067d0` 台账数据迁移 → `tests/migration.test.ts`（迁移逻辑专测）

<!-- covers: t-67e3e4 -->
<!-- covers: t-3067d0 -->
