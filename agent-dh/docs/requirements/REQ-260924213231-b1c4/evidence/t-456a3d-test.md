# t-456a3d 测试记录（父卡 pm 弹框统一来源标志 / T-11「pm 弹框统一来源标志」· 阶段 test）

- 测试时间：2026-09-25T01:53+0800
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`；本卡被测改动为工作区未提交状态，本卡只读不改实现）
- 被测对象（FR-8 / I-7 / TC-14）：
  - **唯一注入点** `packages/web/dsh-pmboard/src/domain/text/pm-badge.ts`（新增，28 行）：`PM_BADGE_PREFIX = '📋 PM · '` + `pmHeader(text)` → `📋 PM · {text}`
  - **四处构造点统一走 `pmHeader`**：`application/use-cases/AskConfirm.ts:135`（确认）、`application/use-cases/AcceptSheet.ts:67`（验收通过）/ `:162`（逐项验收）、`application/internal/capture-mapping.ts:99/113/122/131`（立项四问）、`application/use-cases/HandleFailure.ts:42`（实施链已暂停）
  - **回归测试** `packages/web/dsh-pmboard/tests/pm-question-badge.test.ts`（新增，7 例：前缀+原文、四问、ask_confirm、accept_sheet、失败处置、字面量唯一性、四处构造点经 pmHeader）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts` → 3 files / 38 tests 通过，**exit 0**。验收标准「目标命令输出全绿」达成。另跑全量套件作基线核对：7 files / 8 tests 失败均为本卡无关的存量基线（`Decompose.ts`/`index.ts` 尺寸、`diag-log.ts` 层边界、`RandomIdFactory` 时间戳 id、`render.ts/resolve.ts` 类型等），**pm-badge.ts 与四处构造点零新增门禁违规**。

---

## 1. 目标命令（T-11 验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/pm-question-badge.test.ts tests/capture.test.ts tests/ask-confirm.test.ts --reporter=verbose
```

实际输出（节选关键例，逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/capture.test.ts (17 tests) 126ms
 ✓ tests/pm-question-badge.test.ts > pmHeader：来源标志唯一注入点 > 固定前缀 + 原文
 ✓ tests/pm-question-badge.test.ts > TC-14 四处 pm 弹框 header 均带标志 > 立项四问（两段合计 4 问）header 全部带前缀，题干不变
 ✓ tests/pm-question-badge.test.ts > TC-14 四处 pm 弹框 header 均带标志 > ask_confirm（artifact 确认）header 带前缀，宿主可见的 question 正文不带
 ✓ tests/pm-question-badge.test.ts > TC-14 四处 pm 弹框 header 均带标志 > accept_sheet（逐项 + 最终归档）header 带前缀
 ✓ tests/pm-question-badge.test.ts > TC-14 四处 pm 弹框 header 均带标志 > 失败处置弹框 header 带前缀
 ✓ tests/pm-question-badge.test.ts > TC-14 标志由代码注入，宿主原生提问不带前缀 > 前缀字面量只出现在 pm-badge.ts（别处硬写 = 漂移）
 ✓ tests/pm-question-badge.test.ts > TC-14 标志由代码注入，宿主原生提问不带前缀 > 四处构造点都经 pmHeader（而不是手写前缀）
 ✓ tests/ask-confirm.test.ts (13 tests) 108ms

 Test Files  3 passed (3)
      Tests  38 passed (38)
   Start at  01:52:38
   Duration  611ms (transform 360ms, setup 0ms, collect 653ms, tests 133ms, environment 0ms, prepare 125ms)
```

- 退出码：**0**（全绿，`EXIT=0`）
- 覆盖要点（对应验收：四处 `AskQuestion.header` 均以 `📋 PM · ` 开头；宿主原生 `ask_user_question` 不带该前缀）：
  - ① 立项四问（`buildCaptureQuestions` 两段合计 4 问）header 恰好 = [`需求名称`/`需求类型`/`提示词难度`/`需求文档位置`] 各自 `pmHeader` 结果，且 `question` 正文不以标志开头；
  - ② `ask_confirm` 仅下发 `pmHeader('确认')`，宿主可见 `question` 正文不含标志；
  - ③ `accept_sheet` 逐项（`需求级验收` / `验收项 t-000001`）+ 最终归档（`验收通过`）共 3 个 header 全部带前缀；
  - ④ 失败处置弹框 header = `pmHeader('实施链已暂停')`；
  - ⑤ **代码注入而非 agent 手写**：全 `src/` 扫描下前缀字面量只出现在 `domain/text/pm-badge.ts`（别处硬写 = 漂移）；
  - ⑥ 四处构造点源文件均 `import ... from '../../domain/text/pm-badge.js'` 且含 `pmHeader(`、不含字面量前缀。

## 2. 独立佐证：注入点与调用点（与 ⑤⑥ 同口径的实测）

```bash
cd packages/web/dsh-pmboard && grep -rn "PM_BADGE_PREFIX\\|pmHeader(" src/
```

实际输出：

```
src/application/internal/capture-mapping.ts:99:      header: pmHeader('需求名称'),
src/application/internal/capture-mapping.ts:113:      header: pmHeader('需求类型'),
src/application/internal/capture-mapping.ts:122:      header: pmHeader('提示词难度'),
src/application/internal/capture-mapping.ts:131:      header: pmHeader('需求文档位置'),
src/application/use-cases/AskConfirm.ts:135:        header: pmHeader('确认'),
src/application/use-cases/HandleFailure.ts:42:      header: pmHeader('实施链已暂停'),
src/application/use-cases/AcceptSheet.ts:67:              header: pmHeader('验收通过'),
src/application/use-cases/AcceptSheet.ts:162:            header: pmHeader(it.source.kind === 'requirement'
src/domain/text/pm-badge.ts:18:export const PM_BADGE_PREFIX = '📋 PM · '
src/domain/text/pm-badge.ts:26:export function pmHeader(text): string
```

- 判定：前缀字面量仅在 `pm-badge.ts`（第 18 行定义）；四处构造点全部经 `pmHeader(` —— 与 ⑤⑥ 断言一致。

## 3. 全量套件基线核对（非本卡门禁，仅证「零新增失败」）

```bash
cd packages/web/dsh-pmboard && npx vitest run
```

```
 Test Files  7 failed | 150 passed (157)
      Tests  8 failed | 1850 passed (1858)
```

7 个失败文件均为与本卡无关的存量基线：

| 失败文件 | 失败原因 | 是否涉及 pm-badge / 四处构造点 |
| --- | --- | --- |
| `tests/application/repository.test.ts` | `RandomIdFactory` 期望 6 位 hex，实际时间戳 id `REQ-260925015247-f1e5` | 否 |
| `tests/client-view.test.ts` | archived/canceled 泳道展示 | 否 |
| `tests/language-layer.test.ts` | design/light/feature 语言强度注入 | 否 |
| `tests/layer-boundary.test.ts` | 越界清单仅 `application/internal/diag-log.ts -> node:fs / node:path`（存量） | 否（`pm-badge.ts` 不在清单内） |
| `tests/size-budget.test.ts` | 超标仅 `application/use-cases/Decompose.ts = 401` / `index.ts = 458` | 否 |
| `tests/template-address-injection.test.ts` | 地址段注入一致性（2 例） | 否 |
| `tests/typecheck.test.ts` | 24 个类型错误，分布在 `CaptureHook.ts`/`h3-inject.ts`/`node-input-package.ts`/`domain/template/*`/`gate-wiring.ts` 等 | 否（`pm-badge.ts` 零错误） |

- 结论：本卡改动（新增 `pm-badge.ts` + 四处 header 走 `pmHeader`）**未引入任何新门禁违规**；`pm-question-badge.test.ts` 内嵌的字面量唯一性/构造点守护两例正是防漂移护栏。

## 4. 改动面核对（本卡只读，不改实现）

```bash
git -C . rev-parse HEAD && git -C . branch --show-current
git -C . status --porcelain -- packages/web/dsh-pmboard/src/domain/text/pm-badge.ts packages/web/dsh-pmboard/tests/pm-question-badge.test.ts
git -C . diff --numstat -- <四处构造点>
```

```
9e5ebf60c6714f44d39d8c45783ce4126c9a11e8
main
?? agent-dh/packages/web/dsh-pmboard/src/domain/text/pm-badge.ts
?? agent-dh/packages/web/dsh-pmboard/tests/pm-question-badge.test.ts
5	4	agent-dh/packages/web/dsh-pmboard/src/application/internal/capture-mapping.ts
9	3	agent-dh/packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts
151	270	agent-dh/packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts
2	1	agent-dh/packages/web/dsh-pmboard/src/application/use-cases/HandleFailure.ts
```

- `pm-badge.ts`（28 行）与 `tests/pm-question-badge.test.ts` 为新增未跟踪文件；四处构造点为工作区改动（含同卡其他 FR 的既有改动，`pmHeader` 为其中一处）。
- 本卡未改任何实现文件，仅在验收后写入本测试记录。
