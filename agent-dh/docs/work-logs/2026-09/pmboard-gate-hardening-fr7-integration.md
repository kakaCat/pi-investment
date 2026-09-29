# dsh-pmboard 门禁固化（FR-7 / TC-4）联调记录

- 需求：REQ-260927144541-0481（子卡 t-022248，父卡 t-5e64cd，阶段 integrate）
- 日期：2026-09-27 19:00
- 工作区根：`/Users/yunpeng/pi-investment/agent-dh`
- 联调对象：`tests/tools-schema.test.ts` + `tests/output-contract.test.ts` 所固化的「声明（output.schema）↔ 行为（return 字面量）」门禁
- 结论：**通过**（三源工厂集完全一致；门禁端到端 67 例全绿；TC-4 故障注入确认门禁会变红）

## 1. 联调请求样例 → 期望响应 → 实际返回

### 1.1 请求：三源工厂集一致性（门禁清单 / 工具面导出 / 真实注册点）

三个"谁算一个工具"的事实源必须同一集合——任一源单独漂移，门禁就会"自称全量却漏看"。

```bash
cd packages/web/dsh-pmboard
sed -n '/const FACTORIES = \[/,/\] as const/p' tests/tools-schema.test.ts \
  | grep -oE "'define[A-Za-z]+Tool'" | tr -d "'" | sort > /tmp/A.txt   # A 门禁清单
grep -oE "define[A-Za-z]+Tool" src/tools/index.ts | sort -u > /tmp/B.txt    # B 工具面导出
grep -oE "register\(define[A-Za-z]+Tool" src/index.ts | sed 's/register(//' | sort -u > /tmp/C.txt  # C 真实注册点
diff /tmp/A.txt /tmp/B.txt && diff /tmp/A.txt /tmp/C.txt
```

- **期望响应**：三个集合均为 18，且 A==B==C（diff 无输出）
- **实际返回**：

```
A) FACTORIES 18
B) exports   18
C) register  18
A==B OK
A==C OK
```

判定：✅ 与预期一致。18 个工厂名（A/B/C 同集）：AcceptSheet / Advance / AskConfirm / Capture / ClearPause /
ConfirmReceipt / Create / Decompose / Move / NoteInterruption / RunStatus / Status / Submit / TaskExecute /
TaskMove / TaskReport / TaskStatus / TaskTree。

### 1.2 请求：门禁端到端调用（目标命令）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/tools-schema.test.ts \
  packages/web/dsh-pmboard/tests/output-contract.test.ts
```

- **期望响应**：Test Files 2 passed，Tests 全绿，exit=0
- **实际返回**（2026-09-27 18:59:22）：

```
 ✓ packages/web/dsh-pmboard/tests/tools-schema.test.ts  (40 tests) 9ms
 ✓ packages/web/dsh-pmboard/tests/output-contract.test.ts  (27 tests) 97ms

 Test Files  2 passed (2)
      Tests  67 passed (67)
   Duration  625ms
```

判定：✅ 与预期一致（exit=0）。

### 1.3 请求：TC-4 故障注入（给某工具临时加未声明返回键 → 门禁必红）

在 `output-contract.test.ts` 内以**真实工具源**验证：取 `application/use-cases/TaskTree.ts` 原文 +
真实 `defineTaskTreeTool` 的 `output.schema`，注入未声明键 `gate_fault_injected_undeclared`，走与静态扫描
同一条管线（`returnKeys` → `declaredKeys` → 差集）。注入落在临时副本（`mkdtemp`）上，跑完即删——
**不写真实工作区**（本仓是多窗口共享脏工作树）。

- **期望响应**：注入前原件不含该键；注入后差集包含该键（即：门禁看得见、拦得住）
- **实际返回**：该用例在 1.2 的 27 例中通过；实现见
  `tests/output-contract.test.ts` 的 `describe('输出契约·故障注入…')` 第 3 例
- 判定：✅ 与预期一致

## 2. 联调中发现的偏差（仅记录，未改——不在本卡实施方案内）

`src/index.ts:444` 注册完成后的日志声明与实际注册不一致：

```
'agent tools registered (13): reqboard_create / reqboard_capture / reqboard_status / reqboard_task_run / …
```

- **实际行为**：`src/index.ts` 在 `toolsCtx.effect` 内注册 **18** 个工厂（第 420–441 行）。
- **声明**：日志字符串称 `(13)`，且清单**漏列** `reqboard_run_status` 与 `reqboard_task_tree`。
- **影响**：仅日志观感（不影响功能），但正是本父卡要治的「声明与行为不一致」；schema 级门禁抓不到日志字符串，
  属本卡实施方案（测试侧）范围外，**留待父卡/Lead 决定是否单开一行修复**。已在本子卡汇报的 `next_step` 中登记。

## 3. 复现口径

1. 上述 1.1 / 1.2 命令逐条执行即可复现（工作区根 = `agent-dh`）。
2. 本记录**未**提交 git、**未**构建、**未**重启服务（按卡纪律）。
3. 涉及文件（工作区根相对）：
   - `packages/web/dsh-pmboard/tests/tools-schema.test.ts`
   - `packages/web/dsh-pmboard/tests/output-contract.test.ts`
