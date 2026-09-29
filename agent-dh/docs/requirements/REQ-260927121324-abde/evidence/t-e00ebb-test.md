# t-e00ebb 测试记录（REQ-260927121324-abde · 父卡 t-9b87a6「新增执行与迁移收敛的结构守卫单测」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**通过** —— 目标命令全绿（2 files / 8 tests，exit 0）；两条结构守卫均**经故障注入实测可变红**
> 且违规时精确打印「相对路径:第 N 行 · 式样 → 原文」；排除收敛点后全 src 静态复核零命中。
> 本卡为测试卡：**未改任何源码 / 测试文件**，仅落盘本 evidence 记录。

- 测试时间：2026-09-27 15:13（+08:00）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard` · 工作区根 `/Users/yunpeng/pi-investment/agent-dh`
- 被测交付面（均 **untracked 新增**，由父卡实现卡落盘）：
  - `packages/web/dsh-pmboard/tests/execution-token-guard.test.ts`（108 行）
  - `packages/web/dsh-pmboard/tests/requirement-transition-guard.test.ts`（109 行）
- 被测对象结构事实（只读复核，来源 = 源码文件，2026-09-27 15:13）：
  - 唯一写入口 `src/application/internal/token-usage.ts:160` `task.executions.push(execution)`（`openExecution`，:148）
  - 唯一迁移入口 `src/application/internal/token-usage.ts:291` `req.status = to`（`transitionRequirement`，:271）

---

## 1. 目标命令（父卡口径 · execution-token-guard + requirement-transition-guard）

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts

 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/requirement-transition-guard.test.ts (4 tests) 65ms
 ✓ tests/execution-token-guard.test.ts (4 tests) 122ms

 Test Files  2 passed (2)
      Tests  8 passed (8)
   Duration  527ms
TARGET_EXIT=0
```

- 期望：两条守卫在真实 src 上零违规、且扫描面非空（防扫描器失效假绿）；实际 **8/8 passed，exit 0**。
- 覆盖的 4+4 用例：①扫描面非空断言（execution：src 全量 299 个 .ts，排除后 298；transition：application+http 121 个 .ts，排除后 120）
  ②真实 src 零违规 ③收敛点仍在且仍承担唯一写职责（`openExecution`/`closeExecutions`/`task.executions.push(execution)`；
  `transitionRequirement`/`req.status = to`）④守卫自身可变红 + 读引用/类型声明/注释不误报。

## 2. 故障注入实测（证明守卫非空转，且违规精确报点）

在 `src/application/` 下临时注入 1 个探针文件（含 3 类违规），复跑同一命令，**期望变红**：

```
$ cat src/application/__probe-guard-fault.ts
export function probe(req: any, task: any, execution: any) {
  task.executions.push({ id: 'probe' })        // 第 3 行
  execution.tokenUsage = { totals: null }      // 第 4 行
  req.status = 'implementing'                  // 第 5 行
}

$ npx vitest run tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts
 FAIL  tests/execution-token-guard.test.ts > ... > src 下（token-usage.ts 之外）无 executions.push( 与 tokenUsage 赋值
   → 以下位置绕过唯一写入口（应改经 openExecution / beginExecutionToken / endExecutionToken）：
   src/application/__probe-guard-fault.ts:第 3 行 · executions.push( → task.executions.push({ id: 'probe' })
   src/application/__probe-guard-fault.ts:第 4 行 · tokenUsage 赋值 → execution.tokenUsage = { totals: null }
 FAIL  tests/requirement-transition-guard.test.ts > ... > src/application 与 src/http 内无 req.status / r.status 直接赋值
   AssertionError: 以下位置绕过唯一迁移入口（应改经 transitionRequirement）：
   src/application/__probe-guard-fault.ts:第 5 行 · req.status 直接赋值 → req.status = 'implementing'

 Test Files  2 failed (2)
      Tests  2 failed | 6 passed (8)
```

- 探针清除留痕：`probe leftover: 0`；`git status --porcelain -- src/ | grep -c probe` → `0`（未落常驻文件，跑完即删）。
- 判定：两条守卫均**真实可变红**，且报点格式满足父卡「违规时断言信息打印文件与行号」的要求
  （相对路径 + 第 N 行 + 式样 + 原文）。

## 3. 扩展回归（token 一族 + 两条守卫，防迁移引入回归）

```
$ npx vitest run tests/token-endpoint.test.ts tests/token-fallback.test.ts tests/token-degraded-integration.test.ts \
    tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/ledger-v6-token.test.ts \
    tests/verdicts-and-rework.test.ts tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts

 ✓ tests/token-transition-helper.test.ts (3 tests) 2ms
 ✓ tests/token-usage.test.ts (11 tests) 3ms
 ✓ tests/token-fallback.test.ts (3 tests) 2ms
 ✓ tests/ledger-v6-token.test.ts (8 tests) 39ms
 ✓ tests/requirement-transition-guard.test.ts (4 tests) 67ms
 ✓ tests/execution-token-guard.test.ts (4 tests) 125ms
 ✓ tests/token-endpoint.test.ts (6 tests) 172ms
 ✓ tests/token-degraded-integration.test.ts (9 tests) 241ms
 ✓ tests/verdicts-and-rework.test.ts (10 tests) 278ms

 Test Files  9 passed (9)
      Tests  58 passed (58)
   Duration  856ms
REGRESSION_EXIT=0
```

- `design/test-cases.md` 第 75 行命令另含 `accept-verdicts-snapshot.test.ts` / `rollup-snapshot.test.ts` / `task-move-snapshot.test.ts`
  三份文件**当前不存在**（属其他子卡交付面，本次未落盘），故本卡回归按其**已存在**的文件集执行；缺失项如实标注，不做替代。

## 4. 静态复核（不采信上游自述）

```
# 全 src 扫描（排除唯一收敛点），复核守卫结论
$ grep -rn "executions\.push(\|tokenUsage *=[^=]" src/ --include='*.ts' | grep -v "src/application/internal/token-usage.ts" | wc -l
       0
$ grep -rn "req\.status *=[^=]\|r\.status *=[^=]" src/application src/http --include='*.ts' | grep -v "src/application/internal/token-usage.ts" | wc -l
       0

# 收敛点仍在（排除项不可被删除规避）
$ grep -n "task.executions.push(execution)\|req.status = to\|export function openExecution\|export function transitionRequirement" src/application/internal/token-usage.ts
148:export function openExecution(task: TaskRecord, spec: OpenExecutionSpec, snap?: TokenSnapshot): ExecutionRecord {
160:  task.executions.push(execution)
271:export function transitionRequirement(
291:  req.status = to
```

- 与守卫结论一致：排除收敛点后两处禁用式样**均零命中**；收敛点自身同时是「落执行 + 写 token」（:148/:160）与
  「需求状态迁移」（:271/:291）的唯一入口，guard 内的「收敛点仍存在」断言使其不可被删除规避。

## 5. 边界与说明

- 本卡为 **test 阶段**卡：仅执行目标命令 + 故障注入 + 回归 + 静态复核，**未修改任何源码或测试文件**；
  两条守卫单测为父卡实现卡的 untracked 新增产物，本卡只消费与验证。
- 未越界执行构建/重启（`:13080` 运行实例加载 dist，构建与重启属发布动作，由父卡收口/编排方在会话外处理）。
- 静态守卫只覆盖结构约束，不替代行为用例；行为面（快照带/不带、迁移经收敛点）由其他子卡的 vitest 用例覆盖。

---

**裁决：通过（目标命令全绿 8/8，exit 0；扩展回归 58/58，exit 0；故障注入证明两守卫可变红）。**

测试人：实施子代理（t-e00ebb）；时间：2026-09-27 15:13 (+08:00)
