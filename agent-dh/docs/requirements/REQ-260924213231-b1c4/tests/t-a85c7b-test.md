# t-a85c7b 测试记录（父卡 t-7b5e7a / T-9「实现断点常驻与续跑输入包」· 阶段 test）

- 测试时间：2026-09-25T01:19+0800
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库根 `/Users/yunpeng/pi-investment`，测试工作目录 `agent-dh/packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`，merge: REQ-b1c4 T-1 契约类型与端口）
- 被测对象（FR-6 / I-8；实现为工作区未提交状态，本卡只读不改）：
  - **I-1** `src/application/internal/interruption.ts`（新增，147 行纯函数：`nextActionFor` / `turnEndOutcome`）
  - **I-2** `src/application/use-cases/NoteInterruption.ts`（新增，115 行：`noteInterruption` / `noteInterruptionForWindow`）
  - **I-3** `src/tools/NoteInterruptionTool/NoteInterruptionTool.ts`（新增，58 行工具壳 `reqboard_note_interruption`）
  - 接线改动：`src/adapters/CaptureHook.ts`（+13/-0，onTurnFinished 信号）、`src/application/internal/node-input-package.ts`（+30/-1，`## 断点` 节）、`src/index.ts`（+26/-2，异步边界 + 注册）
  - 回归测试：`tests/interruption-checkpoint.test.ts`（新增，240 行，15 例）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/interruption-checkpoint.test.ts` → 1 file / **15 tests 通过**，**exit 0**。验收标准四条口径（只交棒写 checkpoint / turn\/end 异常原因覆盖 / 重建输入含 `## 断点` 与 pendingAction / 老需求无字段逐字节不变）在 15 例中逐条断言通过。达成「目标命令输出全绿」。

---

## 1. 目标命令（T-9 验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/interruption-checkpoint.test.ts --reporter=verbose
```

实际输出（逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 A（交棒即写 checkpoint） > reqboard_move 交棒 → 台账 interruption.reason=checkpoint 且 pendingAction 非空
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 A（交棒即写 checkpoint） > nextActionFor 是断点与输入包的唯一事实源（各阶段映射）
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 A（交棒即写 checkpoint） > 幂等：同一 stage + 同一 pendingAction 再交棒不重写、不 bump version
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B（turn/end 异常原因补新） > turnEndOutcome 规范化 error / aborted / interrupted；非异常不算中断
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B（turn/end 异常原因补新） > 畸形态（缺 data / 缺 reason / 未知 kind）→ undefined（不猜、不误报）
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B（turn/end 异常原因补新） > 事件路径：checkpoint → 异常原因覆盖（保留按状态重算的 pendingAction）
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B（turn/end 异常原因补新） > CaptureHook turn/end（error）→ onTurnFinished 只发信号；非异常形态不发
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B（turn/end 异常原因补新） > 事件路径永不抛：窗口无绑定需求 / 空 reason → 静默跳过（undefined）
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B′（reqboard_note_interruption 显式兜底） > 工具壳名字/必填 reason 正确（defineTool 构造即编译 schema）
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B′（reqboard_note_interruption 显式兜底） > 补写断点：success + interruption 回执 + 系统评论留痕
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B′（reqboard_note_interruption 显式兜底） > reason 为空 → REQBOARD_INVALID_INPUT；窗口无绑定需求 → REQBOARD_NO_BOUND_REQ
 ✓ tests/interruption-checkpoint.test.ts > 断点常驻 · 写入器 B′（reqboard_note_interruption 显式兜底） > 后写覆盖前写：同一需求始终只保留一个断点对象
 ✓ tests/interruption-checkpoint.test.ts > 续跑输入包（## 断点 节） > 有断点 → 追加「## 断点」，含阶段 / 未完成动作 / 原因 / 时间四要素
 ✓ tests/interruption-checkpoint.test.ts > 续跑输入包（## 断点 节） > 老需求无字段 → 输入包逐字节不变（不出现断点节，段间分隔与改造前一致）
 ✓ tests/interruption-checkpoint.test.ts > 续跑输入包（## 断点 节） > 断点不是需求文档内容：仅台账投影带出（INV-9）

 Test Files  1 passed (1)
      Tests  15 passed (15)
   Start at  01:19:25
   Duration  411ms (transform 150ms, setup 214ms, collect 7ms, environment 0ms, prepare 31ms)
```

- 退出码：**0**（全绿）
- 判定：与拆解计划 T-9 验收「`npx vitest run tests/interruption-checkpoint.test.ts` 全绿：只交棒 → 台账 `interruption.reason==='checkpoint'` 且 pendingAction 非空；喂 `turn/end` 且 `reason.kind='error'` → reason 变 `error:UPSTREAM_STREAM_IDLE:…`；重建输入包含 `## 断点` 与 pendingAction；老需求无字段 → 输入包逐字节不变」逐条一致。

### 1.1 验收四条口径 → 断言落点

| 验收口径 | 断言落点（tests/interruption-checkpoint.test.ts） | 结果 |
|---|---|---|
| 只交棒 → reason=`checkpoint` 且 pendingAction 非空 | :40-52（`toBe('checkpoint')`、`pendingAction === 'reqboard_submit(kind=requirement)'`、`tool === 'reqboard_move'`） | ✓ |
| 喂 turn/end 且 reason.kind=`error` → reason 变 `error:UPSTREAM_STREAM_IDLE:…` | :103-115（`error:UPSTREAM_STREAM_IDLE:stream idle 3m`，stage/pendingAction 保留） | ✓ |
| 重建输入包含 `## 断点` 与 pendingAction | :193-211（四要素 + 段落次序 未决问题 < 断点 < 下一步） | ✓ |
| 老需求无字段 → 输入包逐字节不变 | :213-221（`not.toContain('## 断点')`、`## 未决问题\n（无）\n\n## 下一步`、显式 undefined 逐字节等值） | ✓ |

## 2. 层边界守护（不新增越界）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/layer-boundary.test.ts
```

实际：`Test Files 1 failed | 3 passed`（本命令与 §3 合并跑，见下）；`layer-boundary.test.ts` 唯一失败项的越界清单**只含存量基线**：

```
application/internal/diag-log.ts -> node:fs
application/internal/diag-log.ts -> node:path
```

- 期望：本卡/本需求新增的 application 文件**零越界**。
- 实测佐证（本卡只读核验）：

```bash
for f in src/application/internal/interruption.ts src/application/use-cases/NoteInterruption.ts src/tools/NoteInterruptionTool/NoteInterruptionTool.ts; do
  grep -nE "from .(node:|.*adapters)" "$f" || echo "NONE"
done
```

输出：三个文件均为 `NONE`（不 import `node:`、不 import `adapters`）→ 新增文件**未出现在越界清单**，与期望一致。
- 存量基线证明：`git -C <repo> show HEAD:agent-dh/packages/web/dsh-pmboard/src/application/internal/diag-log.ts | grep -nE "from .(node:|.*adapters)"` → 第 12/13 行 `import * as fs from 'node:fs'` / `import * as path from 'node:path'`，即该越界在 HEAD(`9e5ebf60`) 上**已存在**，非 T-9 引入、非本卡引入。

## 3. 接线回归（额外护栏）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/layer-boundary.test.ts tests/capture-hook.test.ts tests/tools-dispatch.test.ts tests/apply-wiring.test.ts
```

实际输出（节选）：

```
 ✓ tests/apply-wiring.test.ts (4 tests) 16ms
 Test Files  1 failed | 3 passed (4)
      Tests  1 failed | 42 passed (43)
```

- `capture-hook` / `tools-dispatch` / `apply-wiring`（T-9 改动的直接消费方：CaptureHook 信号、工具注册、宿主接线）**全绿**，共 42 例通过。
- 唯一失败为 §2 所述 `layer-boundary.test.ts` 的 `diag-log.ts` 存量基线（HEAD 上即存在）——不因本需求/本卡新增。

## 4. 改动面核验（本卡只读，未触碰实现）

```bash
git -C /Users/yunpeng/pi-investment diff --numstat -- <T-9 涉及文件>
git -C /Users/yunpeng/pi-investment status --porcelain -- <T-9 新增文件>
```

实际输出：

```
13      0   .../src/adapters/CaptureHook.ts
30      1   .../src/application/internal/node-input-package.ts
26      2   .../src/index.ts
--- porcelain ---
?? .../src/application/internal/interruption.ts
?? .../src/application/use-cases/NoteInterruption.ts
?? .../src/tools/NoteInterruptionTool/
?? .../tests/interruption-checkpoint.test.ts
--- wc -l ---
240 tests/interruption-checkpoint.test.ts
147 src/application/internal/interruption.ts
115 src/application/use-cases/NoteInterruption.ts
 58 src/tools/NoteInterruptionTool/NoteInterruptionTool.ts
```

- 上述改动/新增均为 T-9 实施的待提交状态，**本卡未修改任何实现、适配器或测试源码**；本轮新增产物仅本文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-a85c7b-test.md`。
- 用例数与 t-6a3070-integrate 记录一致（15 例），实现自集成验证后未再变化（本卡复跑同数同绿）。

## 5. 测试结论

1. 目标命令 `npx vitest run tests/interruption-checkpoint.test.ts`：**1 file / 15 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成，四条口径逐条有断言落点。
2. 层边界：新增 application 文件零 `node:`/adapters 越界（grep = NONE）；`layer-boundary.test.ts` 唯一失败为 `diag-log.ts` 存量基线（HEAD 即存在）——不因本卡新增。
3. 接线回归：`capture-hook` / `tools-dispatch` / `apply-wiring` 全绿（42 例），T-9 改动的直接消费方未见回归。
4. 本卡为 test 阶段，只执行上述命令并落本记录，未修改任何源码。
