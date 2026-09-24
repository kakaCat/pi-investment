# t-f4d6b1 联调记录（父卡 t-9f96a1 / T-11「pm 弹框统一来源标志」· 阶段 integrate）

- 联调时间：2026-09-25T01:46+0800
- 联调环境：node v22.23.2 · vitest 2.1.9 (darwin-arm64) · HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口 **I-7** `AskQuestion.header` 来源标志契约，FR-8 / UC-5 / TC-14）：
  - 唯一注入点 `packages/web/dsh-pmboard/src/domain/text/pm-badge.ts`（`PM_BADGE_PREFIX='📋 PM · '` + `pmHeader(text)`）
  - → 四处构造点：`src/application/use-cases/AskConfirm.ts:135`、`src/application/use-cases/AcceptSheet.ts:67,162`、`src/application/internal/capture-mapping.ts:99,113,122,131`、`src/application/use-cases/HandleFailure.ts:42`
  - → 通道适配器 `src/adapters/UserQuestionsAdapter.ts:32-46`（把 `AskQuestion[]` 原样交给宿主 `userQuestions.ask`）
  - 契约见 `docs/requirements/REQ-260924213231-b1c4/design/interfaces.md` §I-7、用例 `design/use-cases.md` UC-5、用例 `design/test-cases.md` TC-14
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回**三者一致**（14/14 MATCH）；目标测试 `pm-question-badge.test.ts` 7/7 绿；接口层回归 `tools-dispatch.test.ts` 4/4 绿。

---

## 1. 接口 I-7 三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-t-f4d6b1.test.ts`（跑完即删），在 **真工具壳（`defineAskConfirmTool` / `defineAcceptSheetTool`）→ 真用例（`askConfirm` / `acceptSheet` / `openFailurePopup` / `buildCaptureQuestions`）→ 真适配器（`UserQuestionsAdapter`）→ 假宿主 `userQuestions` 服务**的完整链路上，捕获 pm 侧**实际交给宿主的** `AskQuestion[]`，逐条打印「请求样例 / 期望响应 / 实际返回」。窗口 `session-probe-t11`。

### A. `reqboard_ask_confirm`（真工具，弹框路径）

请求样例：`reqboard_ask_confirm({ target: 'artifact', kind: 'requirement', question: '确认需求文档？', advance: false })`

宿主实际收到的请求（探针捕获，原始）：

```json
{"id":"confirm","header":"📋 PM · 确认"}
```

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| 宿主收到的 `header` | `pmHeader('确认')` = `"📋 PM · 确认"` | `"📋 PM · 确认"` | MATCH |
| `question` 正文字面量（标志只在 header） | 不含 `"📋 PM · "` | 不含 | MATCH |
| 工具返回 `success` | `true` | `true` | MATCH |
| 工具返回 `confirmed` | `true` | `true` | MATCH |
| 工具返回 `advanced` | `false`（`advance:false`） | `false` | MATCH |
| 工具返回 `from`/`to` | `"brainstorming"` / `"brainstorming"` | `"brainstorming"` / `"brainstorming"` | MATCH |

### B. `reqboard_accept_sheet`（真工具，逐项 + 最终归档）

请求样例：`reqboard_accept_sheet({ requirement_id: 'REQ-000001' })`（验收单 2 项 pending）

宿主实际收到的三批请求 header（探针捕获，原始）：

```json
["📋 PM · 需求级验收","📋 PM · 验收项 t-000001","📋 PM · 验收通过"]
```

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| 逐项（需求级）| `pmHeader('需求级验收')` | `"📋 PM · 需求级验收"` | MATCH |
| 逐项（任务级，经 `fmt` 拼 taskId）| `pmHeader('验收项 t-000001')` | `"📋 PM · 验收项 t-000001"` | MATCH |
| 最终归档确认 | `pmHeader('验收通过')` | `"📋 PM · 验收通过"` | MATCH |
| 工具返回 `success`/`passed`/`failed` | `true` / `2` / `0` | `true` / `2` / `0` | MATCH |

### C. 立项四问（`buildCaptureQuestions` 构造，CaptureTool 的弹框内容）

请求样例：`buildCaptureQuestions(['候选 A'])`

构造出的四条 `header`（探针捕获，原始）：

```json
["📋 PM · 需求名称","📋 PM · 需求类型","📋 PM · 提示词难度","📋 PM · 需求文档位置"]
```

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| 第 1 问 header | `pmHeader('需求名称')` | `"📋 PM · 需求名称"` | MATCH |
| 第 2 问 header | `pmHeader('需求类型')` | `"📋 PM · 需求类型"` | MATCH |
| 第 3 问 header | `pmHeader('提示词难度')` | `"📋 PM · 提示词难度"` | MATCH |
| 第 4 问 header | `pmHeader('需求文档位置')` | `"📋 PM · 需求文档位置"` | MATCH |
| 问项条数（两段合计） | `4` | `4` | MATCH |

### D. 失败处置弹框（`openFailurePopup`）

请求样例：`openFailurePopup(deps, 'REQ-000001', { agent: { id: W } })`

宿主实际收到的请求（探针捕获，原始）：

```json
{"header":"📋 PM · 实施链已暂停"}
```

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| 宿主收到的 `header` | `pmHeader('实施链已暂停')` | `"📋 PM · 实施链已暂停"` | MATCH |
| 返回值（选中「重跑该卡」）| `"rerun"` | `"rerun"` | MATCH |

### E. 对照：宿主原生提问不带前缀（不误伤）

请求样例：同一假宿主服务，直接下发宿主原生问题 `{ id: 'host-1', header: '宿主原生提问', question: '你确认吗？' }`（不经 `pmHeader`）。

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| `header` 是否以 `"📋 PM · "` 开头 | `false`（宿主原生不带标志） | `false` | MATCH |

**探针汇总：14/14 MATCH → `Test Files 1 passed` / `Tests 5 passed`（exit 0）。**

## 2. 目标命令：本卡目标测试（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/pm-question-badge.test.ts
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/pm-question-badge.test.ts (7 tests) 15ms

 Test Files  1 passed (1)
      Tests  7 passed (7)
```

- 退出码：**0**（全绿）
- 7 例锁定：`pmHeader` 固定前缀 + 原文；立项四问 header 全带前缀且正文不带；ask_confirm 弹框 header 带前缀；accept_sheet（逐项+最终）三处 header 带前缀；失败处置 header 带前缀；**前缀字面量只出现在 `domain/text/pm-badge.ts`**（别处硬写 = 漂移，静态扫描断言）；**四处构造点都 import `pmHeader` 且不硬写字面量**。

## 3. 接口层回归（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/pm-question-badge.test.ts tests/tools-dispatch.test.ts
```

实际输出：

```
 ✓ tests/tools-dispatch.test.ts (4 tests) 4ms
 ✓ tests/pm-question-badge.test.ts (7 tests) 15ms

 Test Files  2 passed (2)
      Tests  11 passed (11)
```

- 退出码：**0** —— 工具壳分派链（含 `reqboard_ask_confirm` 的 evidence/弹框分派）未因 header 改动回归。

## 4. 联调结论

1. 接口 I-7 的**请求样例 → 期望响应 → 实际返回**三方一致（14/14 MATCH）：四处 pm 侧构造点（ask_confirm / accept_sheet 逐项+最终 / 立项四问 / 失败处置）下发给宿主的 `AskQuestion.header` 均以固定前缀 `📋 PM · ` 开头；题干正文不被注入（标志在 header，不在 question）；宿主原生提问不经 `pmHeader`、不带前缀。FR-8「不读正文即可分辨来源，且标志由 pm 侧代码注入、不靠 agent 手写」在本轮实测成立。
2. 目标测试 `pm-question-badge.test.ts` 7/7 绿（exit 0），接口层回归 `tools-dispatch.test.ts` 4/4 绿。
3. 本卡为 integrate 阶段：联调走**临时探针**（运行后已删除），**未修改任何实现或测试源码**，本轮新增产物仅本文件。
4. 工作区状态：`src/domain/text/pm-badge.ts`（新增）+ 四处构造点 + `tests/pm-question-badge.test.ts` 为父卡 T-11（`t-9f96a1`）的待提交改动（本卡未触碰）；HEAD = `9e5ebf60`（branch `main`）。
