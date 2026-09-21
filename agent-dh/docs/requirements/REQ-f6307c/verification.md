# REQ-f6307c 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：REQ-f6307c 完成。核心发现——「Agent 跳过立项弹框」并非 Hook 链路断链（T2 的"apply 未执行"判定是观测面误诊：查错日志路径/launchd 日志停更/stdout 死管道三重错误），链路本身全程通畅。实际修复：新增文件化诊断通道 captureDiag（state/reqboard-capture-diag.log，双写防 stdout 蒸发），5 节点全接入；真实窗口 E2E 证实 unbound 消息会注入 1179 字动态提示词并弹出立项框（用户确认）；模拟 3 轮连续测试 100% PASS；bound 窗口零噪音、性能 0.041ms。4 个任务全部 done，验收标准已全部修订为可执行命令。

## 1. 验收列表

### v1-1 · 在 Hook 注入链路的 5 个关键节点添加诊断日志

**验收内容**：【在 Hook 注入链路的 5 个关键节点添加诊断日志】验收：怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && grep -c "captureDiag" dist/index.mjs → 输出 ≥10（5 节点 + EARLY 均已接入双写）
2. 命令：cat agent-dh/.dsh-data/state/reqboard-capture-diag.log | grep -E "EARLY|NODE-[1-5]" → 每类标记至少 1 条（EARLY/NODE-1/NODE-2/NODE-4/NODE-5 均有实录）
3. 界面路径：打开任意 unbound 窗口发消息 → 上述 diag 文件实时新增 NODE-2/3/4/5 行（tail -f 可见）

**操作步骤**：
1. 怎么验（可执行）：
2. 1. 命令：cd agent-dh/packages/pages/dsh-pmboard && grep -c "captureDiag" dist/index.mjs → 输出 ≥10（5 节点 + EARLY 均已接入双写）
3. 2. 命令：cat agent-dh/.dsh-data/state/reqboard-capture-diag.log | grep -E "EARLY|NODE-[1-5]" → 每类标记至少 1 条（EARLY/NODE-1/NODE-2/NODE-4/NODE-5 均有实录）
4. 3. 界面路径：打开任意 unbound 窗口发消息 → 上述 diag 文件实时新增 NODE-2/3/4/5 行（tail -f 可见）

**预期结果**：按上述步骤执行后满足验收标准：怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && grep -c "captureDiag" dist/index.mjs → 输出 ≥10（5 节点 + EARLY 均已接入双写）
2. 命令：cat agent-dh/.dsh-data/state/reqboard-capture-diag.log | grep -E "EARLY|NODE-[1-5]" → 每类标记至少 1 条（EARLY/NODE-1/NODE-2/NODE-4/NODE-5 均有实录）
3. 界面路径：打开任意 unbound 窗口发消息 → 上述 diag 文件实时新增 NODE-2/3/4/5 行（tail -f 可见）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 执行诊断测试，找到链路断链位置

**验收内容**：【执行诊断测试，找到链路断链位置】验收：怎么验（可执行）：
1. 命令：cat agent-dh/docs/requirements/REQ-f6307c/diagnostic-log.txt → 含「T2 误诊的三重观测错误」完整分析（查错路径/launchd 停更/stdout 死管道）与最终结论（链路未断，观测面失效）
2. 命令：grep "NODE-1.*SUCCESS" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 有输出即证明 apply() 实际正常执行（推翻"未执行"初判）
3. 数据可查：.dsh-data/state/reqboard-capture-diag.log 含 EARLY/NODE-1/2/4/5 全部标记（文件化观测面已落地）

**操作步骤**：
1. 怎么验（可执行）：
2. 1. 命令：cat agent-dh/docs/requirements/REQ-f6307c/diagnostic-log.txt → 含「T2 误诊的三重观测错误」完整分析（查错路径/launchd 停更/stdout 死管道）与最终结论（链路未断，观测面失效）
3. 2. 命令：grep "NODE-1.*SUCCESS" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 有输出即证明 apply() 实际正常执行（推翻"未执行"初判）
4. 3. 数据可查：.dsh-data/state/reqboard-capture-diag.log 含 EARLY/NODE-1/2/4/5 全部标记（文件化观测面已落地）

**预期结果**：按上述步骤执行后满足验收标准：怎么验（可执行）：
1. 命令：cat agent-dh/docs/requirements/REQ-f6307c/diagnostic-log.txt → 含「T2 误诊的三重观测错误」完整分析（查错路径/launchd 停更/stdout 死管道）与最终结论（链路未断，观测面失效）
2. 命令：grep "NODE-1.*SUCCESS" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 有输出即证明 apply() 实际正常执行（推翻"未执行"初判）
3. 数据可查：.dsh-data/state/reqboard-capture-diag.log 含 EARLY/NODE-1/2/4/5 全部标记（文件化观测面已落地）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 根据诊断结果修复 Hook 注入链路

**验收内容**：【根据诊断结果修复 Hook 注入链路】验收：怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-capture-chain.mts → 输出 "PASS：unbound 全链路通畅"，DYNAMIC PROMPT text.length=1179>0
2. 命令：grep -E "NODE-1.*SUCCESS|DYNAMIC PROMPT" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 真实环境 5 节点日志齐全
3. 界面路径（用户已于 2026-09-21 10:31 实测确认）：新开 unbound 窗口发工作意图消息 → Agent 弹出立项三问弹框（reqboard_capture 首调）

**操作步骤**：
1. 怎么验（可执行）：
2. 1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-capture-chain.mts → 输出 "PASS：unbound 全链路通畅"，DYNAMIC PROMPT text.length=1179>0
3. 2. 命令：grep -E "NODE-1.*SUCCESS|DYNAMIC PROMPT" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 真实环境 5 节点日志齐全
4. 3. 界面路径（用户已于 2026-09-21 10:31 实测确认）：新开 unbound 窗口发工作意图消息 → Agent 弹出立项三问弹框（reqboard_capture 首调）

**预期结果**：按上述步骤执行后满足验收标准：怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-capture-chain.mts → 输出 "PASS：unbound 全链路通畅"，DYNAMIC PROMPT text.length=1179>0
2. 命令：grep -E "NODE-1.*SUCCESS|DYNAMIC PROMPT" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 真实环境 5 节点日志齐全
3. 界面路径（用户已于 2026-09-21 10:31 实测确认）：新开 unbound 窗口发工作意图消息 → Agent 弹出立项三问弹框（reqboard_capture 首调）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 连续测试与回归验证

**验收内容**：【连续测试与回归验证】验收：怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-t4-rounds.mts → 输出 "连续测试: 3/3 100% PASS" 且每轮 turn/end 清除 OK
2. 命令：grep "windowBound=true" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 有输出即 bound 窗口零噪音回归通过
3. 性能命令：node --import tsx/esm /tmp/perf-diag.mts → captureDiag avg 0.041ms << 100ms（脚本内容见 tests/test-report.md §4）
4. 文件存在性：ls docs/requirements/REQ-f6307c/diagnostic-log.txt → 诊断日志已保存

**操作步骤**：
1. 怎么验（可执行）：
2. 1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-t4-rounds.mts → 输出 "连续测试: 3/3 100% PASS" 且每轮 turn/end 清除 OK
3. 2. 命令：grep "windowBound=true" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 有输出即 bound 窗口零噪音回归通过
4. 3. 性能命令：node --import tsx/esm /tmp/perf-diag.mts → captureDiag avg 0.041ms << 100ms（脚本内容见 tests/test-report.md §4）
5. 4. 文件存在性：ls docs/requirements/REQ-f6307c/diagnostic-log.txt → 诊断日志已保存

**预期结果**：按上述步骤执行后满足验收标准：怎么验（可执行）：
1. 命令：cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-t4-rounds.mts → 输出 "连续测试: 3/3 100% PASS" 且每轮 turn/end 清除 OK
2. 命令：grep "windowBound=true" agent-dh/.dsh-data/state/reqboard-capture-diag.log → 有输出即 bound 窗口零噪音回归通过
3. 性能命令：node --import tsx/esm /tmp/perf-diag.mts → captureDiag avg 0.041ms << 100ms（脚本内容见 tests/test-report.md §4）
4. 文件存在性：ls docs/requirements/REQ-f6307c/diagnostic-log.txt → 诊断日志已保存

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 测试证据报告: docs/requirements/REQ-f6307c/tests/test-report.md
- 代码评审报告: docs/requirements/REQ-f6307c/reviews/code-review.md
- 诊断文档（误诊修正+修复+验证实录）: docs/requirements/REQ-f6307c/diagnostic-log.txt
- 真实环境链路实录: .dsh-data/state/reqboard-capture-diag.log（EARLY/NODE-1 SUCCESS + session-f65bdd85 全链 DYNAMIC 1179字）
- 集成验证命令: cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-capture-chain.mts（PASS）
- 连续测试命令: node --import tsx/esm scripts/verify-t4-rounds.mts（3/3 100% PASS）
- 性能: captureDiag 0.041ms/次（N=100），预算 <100ms
- 用户确认: 测试窗口 session-f65bdd85 弹出立项三问弹框（2026-09-21 10:31，真实 E2E 第 1 次）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 在 Hook 注入链路的 5 个关键节点添加诊断日志 | ✓ 通过 | human/session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a | 2026-09-21 19:16 |
| v1-2 | 执行诊断测试，找到链路断链位置 | ✓ 通过 | human/session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a | 2026-09-21 19:16 |
| v1-3 | 根据诊断结果修复 Hook 注入链路 | ✓ 通过 | human/session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a | 2026-09-21 19:16 |
| v1-4 | 连续测试与回归验证 | ✓ 通过 | human/session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a | 2026-09-21 19:16 |
| v1-5 | 需求级验收 | ✓ 通过 | human/session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a | 2026-09-21 19:16 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a | 2026-09-21 19:19 |
