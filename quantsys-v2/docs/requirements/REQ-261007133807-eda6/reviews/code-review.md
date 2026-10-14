# 评审报告（REQ-261007133807-eda6）

**评审方式**：本次为单窗口交付，**无独立评审人**——故本报告是**自查式评审**：
按 `design/` 六份文档逐条对照实现，并给出可复核命令。**不声称"第三方评审"**。

## 一、逐条对照（设计 ↔ 实现）

| 设计条目 | 期望 | 实测 | 结论 |
|---|---|---|---|
| `architecture.md` §目标：判据收敛为**一个**纯函数出口 | 三处判定（checker 三条路径 / disposition L2 / level_resolver 映射）全部经出口 | `decide_escalation` 为唯一判定；`should_escalate` 与 `disposition.decide` 均为壳/映射；`level_resolver` 不动（只管 P 档） | ✅ |
| `architecture.md` §裁决顺序（15 行顺序表） | 12 步偏移严格递增、与文档同序 | 函数体内 12 步偏移 699<908<1035<1246<1386<2038<2324<2686<2964<3161<3313 | ✅ |
| `architecture.md` §数据流顺序 | 裁决 → 处置 → 去重覆盖 → 落库/通知 | `engine.py` 语句偏移 judge 4495 < decide 5027 < dedup 5194 < notify 7494 | ✅ |
| `architecture.md` §不做：不把 level_resolver 折进出口 | 渲染/SLA 口径不受影响 | `level_resolver.py` 零改动；`test_level_router.py` 全绿 | ✅ |
| `data-model.md` §两列而非三列 | 无第三列"命中路径" | `watch_triggers` 仅加 `escalation_code` / `escalation_reason` | ✅ |
| `data-model.md` §迁移两库 + lock_timeout + 幂等 | 两库都跑、可复跑 | 两库 `--apply` exit 0；复跑打印「（无，已就绪）」；脚本内 `SET lock_timeout='30s'` | ✅ |
| `data-model.md` §不回填历史行 | 89 行如实 NULL | `quant_investment` 89/89 为 NULL（迁移 verify 输出） | ✅ |
| `interfaces.md` §IF-1~IF-9 全部有实现 | 9 条接口齐备 | 逐条见 `tests/evidence.md` 与卡汇报（IF-5 两列落库、IF-8 两条渲染路径等） | ✅ |
| `interfaces.md` §IF-6/IF-7 纯追加 | 既有字段原样保留 | 用例断言响应同时含 `escalation_policy` 原值；存量 NULL 读后仍 NULL | ✅ |
| `test-cases.md` TC-1~TC-10 | 逐条可跑 | 26/6/10/22/92/4 passed（见证据文档） | ✅ |
| `backend.md` §无新增开关/索引/CHECK | 三项都没有 | 迁移脚本无 `CREATE INDEX`、无 `CHECK`；无新环境变量 | ✅ |
| `backend.md` §写库失败不阻断通知 | 自吞 + 留痕 | 用例断言 `facade.sent == 1` 且 stdout 含「触发记录落库失败」 | ✅ |
| `use-cases.md` UC-1「没叫的卡不写理由」 | 卡面只写"叫"的理由 | 新增 `should_render_reason`：已知非唤醒码 + 无理由 → 不渲染（用例覆盖 4 个码） | ✅ |

## 二、评审发现（如实列出，含未修项）

1. **对设计字面的一次偏离（已记账）**：`design/backend.md` 写「`EscalationPolicy.default()` 取
   `EscalationChecker.DEFAULT_ANOMALY_CHANGE_PCT`」——照字面做会成环（`models → checker`，而
   checker 依赖 models）。实现改为：常量落在 `models`，两处引用同一值。**语义（唯一事实源）未变，
   导入方向变了**。复核命令：`grep -rn "DEFAULT_ANOMALY_CHANGE_PCT" domain/ | grep -v __pycache__`。
2. **卡面覆盖边界（未修，已登记）**：P0 与 P1 首项走 `_skeleton_lines` → 有「升级原因」行；
   **P1 其余项与 P2/P3 聚合摘要是一行式，不显示该行**。判断：聚合摘要是知悉类文本，
   每行挂理由会变噪音；FR-3 针对卡面正文，未要求聚合摘要。若要覆盖，属新需求。
3. **`should_render_reason` 是评审期收紧的语义**：`test-cases.md` 原先只说「无理由隐藏」；
   端到端核对时发现"预算门/观察类"的**码**也会被下发（t8 起），若照码渲染会让每张知悉类卡
   多一行「升级原因：观察类」——自相矛盾。现判据：有理由 → 渲染；码意味着叫 agent → 渲染；
   码未收录 → 渲染（响亮）；已知非唤醒码且无理由 → 不渲染。**设计与实现已对齐**（本条已回写文档）。
4. **测试替身签名跟进（测试侧改动，非行为变更）**：`WatchNotifier.notify` 新增关键字
   `escalation_code` 后，`tests/application/test_watch_disposition_engine.py` 的 `FakeNotifier`
   固定签名不匹配 → 引擎把 TypeError 当"通知失败"吞掉 → 用例红。已给替身补参数（断言内容未改）。
5. **一处生产库误写（已清理，如实记账）**：用独立 python 探针跑路由做回读时，`PGDATABASE`
   被 `.env` 覆盖，误在 `quant_investment` 建了 2 条探针规则（id 33/34）——已逐条删除并复核残留 0；
   同类防线已固化：回读断言写进 pytest 用例（conftest 负责切库）。
6. **子卡验收模板跨仓（流程问题，非代码问题）**：插件自动生成的子卡阶段文本写
   `npx vitest run tests/` / `pnpm test`，本仓是 Python/pytest。处理：按本仓栈执行等价命令，
   并在每张子卡汇报里显式标注不一致（不改卡文）。
7. **删除了一个私有死代码**：`disposition._meta_gate`（元触发轻门）在判定迁出后无任何引用，
   随旧判定体一并删除；`evaluate_meta_trigger` 等公开符号一律保留。

## 三、反向证据（避免"只列好消息"）

- **理由并非从零可查**：`escalated` 分支原本就把「原始原因」折进 `disposition_reason`；
  本需求的增量是**结构化 + 覆盖全部结局 + 卡面可见**，不是"第一次记录原因"。
- **本机库样本小**：`quant_investment` 89 条触发、7 条规则、`escalated` 0 条——
  只能证明"库里结构上不带理由码、存量规则全无策略"，**不能**推断线上从未唤醒过 agent。
- **`EscalationChecker` 三条路径未被质疑**：它们是 `REQ-c9f899 t7` 的收敛结果，本需求只做
  收敛与可见化，未改动其判据口径。
