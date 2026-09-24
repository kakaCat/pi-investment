# 验收清单（{{REQ_ID}}）

**交付结论**：（做了什么、验了什么——一句话）

## 证据（可复核，禁止"功能正常"这类空话）

- 命令 + 输出摘要：
- 报告/截图路径：
- 关键数据（对比前后：延迟、错误率、覆盖率）：
- 覆盖对照终态：decomposition.md 覆盖对照（N 条款全覆盖、豁免 M 条）+ TC-x 执行结果（通过 N/N）

## 验收项（按需求条款逐条生成，submit 时自动转为验收单）

（本节由窗口根据 requirement.md 功能点表 + decomposition.md 覆盖对照生成：
每个 FR-x（或 BUG-x/RF-x 等）一行，验收标准从需求文档的验收标准列抄过来。
submit 本文档后自动进 acceptance_sheet，人工通过 reqboard_accept_sheet 弹框逐项验收。）

| 条款 | 验收标准 | 证据引用 |
|---|---|---|---|
| FR-1 | （从 requirement.md 对应条款的验收标准抄过来——可证伪：跑什么、看到什么算过） | TC-x / test-evidence 第 N 节 / 截图路径 |
| FR-2 | ... | ... |

## 未覆盖/已知限制

（诚实列出）

## 文档完整性

9 类文档口径（requirement / design 四份 / decomposition / tasks 每任务一份 / reviews 非空 / tests 非空）——缺失清单见验收单。

---
**验收流程**：submit 本文档 → 后端自动生成验收单（acceptance_sheet，每条款一个验收项）→ reqboard_accept_sheet 弹框逐项验收（通过/改进/其他）→ 验收结论归档进 archived/retro.md
