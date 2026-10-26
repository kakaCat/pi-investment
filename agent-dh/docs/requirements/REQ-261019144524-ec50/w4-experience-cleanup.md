# 经验库噪声处置方案（unknown-symbol 记录清单与建议）

> **处置状态：✅ 已执行（2026-10-20，w-503df447，用户指令「继续」授权按建议执行）**——B/C 21 条→decision、D 64 条→knowledge、E 185 条→data（因 CHECK 约束仅允许 knowledge/experience/decision/data，E 桶落 data 并带 archived_from 元数据标记）；全程零物理删除（总数 3534 不变），experience_stats 复核 total=73、unknown=0、untagged=0。备份：quantsys-v2/backups/2026-10-20-input-governance/memories_full_20261020.sql；契约登记：data_contracts.json governance=experience_category_cleanup_20261020。

- **需求**：REQ-261019144524-ec50 进化闭环有效性改造（SP-4 / W5）
- **任务**：t-9bae04（analysis · backend）
- **落盘**：2026-10-19 · w-503df447（investor）；全程只读，**未删除/修改任何记录**
- **数据来源**：quant_investment.memories 表直查（psql，category='experience'，全量 343 条）、experience_stats 实调（2026-10-19）、memory_search 抽样阅读（2026-10-19）

## 0. 口径修正（重要）

需求 §2.1 的「200 条经验中 155 条 unknown」是 **experience_stats 工具 limit=200 的截断样本**（该工具 limit 即拉取上限，2026-10-19 实调 total=200 恰为上限值）。**库内真值（psql 全量）= 343 条**，其中前导真实标的代码 73 条、非标的 270 条（78.7%）。本方案以下全部以 DB 全量为准。

## 1. 噪声聚类盘点（343 条全量五分桶）

| 桶 | 条数 | 形态 | 结局标签分布 | 时间分布 |
|---|---|---|---|---|
| **A. 真实标的**（前导 6 位代码，除 000000） | **73** | `600887 交易经验（…）`，场景/结果/盈亏完整 | profit 3 / loss 12 / neutral 58 | 08 月 6、09 月 59、10 月 8（仍在增长） |
| **B. 伪代码 000000** | **8** | 账户/系统级事件借用占位代码 | profit 1 / neutral 7 | 全部 09 月 |
| **C. 伪代码 SYSTEM** | **13** | `SYSTEM 交易经验（…）` | profit 2 / loss 9 / neutral 2 | 全部 09 月 |
| **D. JSON 信封** | **64** | `{"kind":"experience","source":"distiller","provenance":{"channel":"chan_weekly",…}}`——2026-08 一次性从 agent_knowledge 迁移的策略回测蒸馏（缠论买点胜率、min_roe≥15 规则等） | 全 0 标签 | 全部 08 月（一次性迁移） |
| **E. 无 symbol 文本** | **185** | `【盯盘触发处置·闭环】`、`工程教训（…）`、`REQ-xxx 修复`、`2026-09-14（w-xxx）`等工程/流程/复盘记录 | profit 1 / loss 3 / neutral 7 / 余 untagged | 09 月 175、10 月 1（**流入已自然停止**） |

经验_stats 的「胜率 1.5%、untagged 139」就是被 B/C/D/E 稀释的结果——**A 桶才是唯一有效的交易经验样本基**。

## 2. 抽样阅读结论（各桶价值判断）

- **A 桶**：真实交易复盘（如 601600 突破回踩、300720 未挂止损暴跌 -10.5%），是 R-008 决策前检索的唯一有效语料——**保留**。
- **B/C 桶（21 条）**：内容多为盯盘误触发、账户巡检等系统事件，pnl 标签（C 桶 loss 9）直接污染胜率统计——**隔离**。
- **D 桶（64 条）**：策略级回测知识（非个股经验），内容本身有效但归错命名空间，且 JSON 信封使工具 symbol 解析恒失败——**隔离**（迁移 category=knowledge 更贴切）。
- **E 桶（185 条）**：工程教训/REQ 流程记录。抽样 6 条（2026-09-28 w-f559e57b 系列、盯盘状态机、通知旁路清理等）确认：内容有长期价值但**不属交易经验**，且大部分已被蒸馏进 genome lessons「工程纪律」章节（wrap 污染、schema 契约、门禁实测等均有对应）——**建议作废**（归档标记，不物理删除）。

## 3. 三类处置方案（记录数与理由；执行待用户裁决）

| 处置 | 条数 | 范围 | 方式 | 理由 |
|---|---|---|---|---|
| **保留** | **73** | A 桶全部 | 不动 | 唯一有效交易样本基；R-008 检索与 experience_stats 胜率的正当分母 |
| **隔离** | **85** | B 8 + C 13 + D 64 | 批量改 category（B/C→decision 或 archived 标记；D→knowledge），**不删除** | 内容有证据价值但污染交易统计与检索；D 桶归 knowledge 后仍可供策略研究复用 |
| **作废** | **185** | E 桶全部 | 批量标记 archived（status 字段或迁出 experience 命名空间），**不物理删除**；作废前抽查 10% 确认关键教训已入 genome lessons，未覆盖的先蒸馏再作废 | 命名空间误置的工程记录；78.7% 噪声的主体，清除后经验库统计才可用 |

**执行前提（用户裁决点）**：①隔离/作废的批量 UPDATE 需用户确认后执行，执行前 `pg_dump` 备份 memories 表并落 decision_audit + memory 留痕（R-020）；②本方案未动任何记录，`experience_stats` total 若变化只能来自新写入，可解释。

## 4. 今后经验写入的 symbol 必填纪律（建议条款，交用户确认后进基因组）

1. **symbol 必填且为真实代码**：experience_write 的 symbol 必须为该经验直接关联的 6 位 A 股代码；**禁用伪代码**（unknown / SYSTEM / 000000 / 指数代码冒充个股）。
2. **无关联标的的经验禁止进 experience 命名空间**：工程/流程/系统类教训 → memory_write(namespace=default) 或蒸馏进 genome lessons；账户级（无单一标的）复盘 → decision 命名空间并标注账户。
3. **工具层硬校验建议**（另立卡，不在本需求边界）：experience_write 增加 symbol 格式校验（^\d{6}$ 且非 000000）与命名空间路由守卫，拒绝即报错不静默兜底。
4. **例行核查**：周报 KPI 段（w2 §5）顺带核查 experience_stats 中 unknown 占比，>5% 告警并追查写入源。

## 5. 验收锚点（本卡三项）

- [x] **报告落盘**：本文件（w4-experience-cleanup.md），含三类处置的记录数与理由（§3：保留 73 / 隔离 85 / 作废 185）。
- [x] **symbol 必填纪律条款**：§4 四条（含工具层校验建议与例行核查）。
- [x] **无静默删除**：本卡全程只读（psql SELECT / experience_stats / memory_search），库内 343 条零改动；处置动作全部列为待用户裁决项（§3 执行前提）。

## 6. 边界与置信度

- **高置信**：五桶分类与计数（psql 全量分组，2026-10-19）；D 桶为 08 月一次性 distiller 迁移（provenance 字段实证）；E 桶流入已停止（10 月仅 1 条）。
- **中置信**：E 桶「大部分已蒸馏进 genome lessons」基于 6 条抽样 + lessons 章节对照，作废前的 10% 抽查不可省。
- **边界**：①只覆盖 memories 表 category='experience'，不含 knowledge（1463 条）与 data（1723 条）桶的卫生；②experience_stats 工具 limit 截断问题（统计口径与库内真值偏离）建议另立卡修（报表工具应按全量聚合或显式声明截断）。
