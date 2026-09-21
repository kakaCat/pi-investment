---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 架构设计（REQ-2d1c74）

## 1. 目标与总体方案（serves: FR-2, FR-3）

**目标（可证伪）**：feature 需求的 design→decomposing 转移，在文档集未交齐、设计文档未全部确认、
或设计文档含拆分内容时，被代码级拒绝并给出缺口清单；文档集齐全且全部确认后正常放行。

总体方案 = 五个相互独立的加固件，全部落在既有 G2 门上，**不新增/删除阶段与闸门**：

1. 文档集扩展（FR-1）：category-doc-sets 支持条件必交文档与豁免声明；
2. 完整性校验前移（FR-2）：design→decomposing 前代码级核验文档集 + 成组确认；
3. 拆分内容硬门禁（FR-3）：三条确认通道落章前扫描 design/*.md；
4. 规范层纠错（FR-4）：提示词片段与工作流指南消除 2026-09-21 裁定前的语义残留；
5. 登记可打开性校验（FR-5）：产物登记时即拦下不存在/伪路径。

## 2. 模块改动地图（serves: FR-1, FR-2, FR-3, FR-5）

| 模块（相对 packages/pages/dsh-pmboard/src/） | 改动 | 服务的功能点 |
|---|---|---|
| application/internal/category-doc-sets.ts | DELTA 扩字段 + 策略解析 | FR-1 |
| application/internal/content-gates.ts | 新增拆分内容检测纯函数 | FR-3 |
| application/internal/content-gate-wiring.ts | 新增两个闸门装配函数 | FR-2, FR-3 |
| application/internal/artifact-gates.ts | GateFailure 扩码 + design 成组确认判定 | FR-2, FR-3 |
| application/use-cases/ConfirmArtifact.ts、AskConfirm.ts | 落章前扫描 + 成组落章 | FR-2, FR-3 |
| application/use-cases/MoveRequirement.ts、AskConfirm.ts 推进块 | 转移前调完整性闸门 | FR-2 |
| application/use-cases/SubmitArtifact.ts | 登记前可打开性校验 | FR-5 |
| adapters/ArtifactSync.ts | 登记路径形态防御性过滤 | FR-5 |
| http/routers/requirements.ts | 看板确认/推进两入口同样接线 | FR-2, FR-3 |
| application/internal/design-docs.ts、client/stage-panel.ts | 条件文档/豁免的呈现投影 | FR-1 |
| domain/prompt/fragments/design/heavy/overrides.md、docs/guides/reqboard-workflow.md | 过时指令修正 | FR-4 |

## 3. 分层与数据流（serves: FR-2, FR-3）

依赖方向单向：domain（纯判定，零 IO）→ application/internal（取数装配，唯一碰 DocsReader 处）
→ use-cases / http（调用点）。新增判定一律进 domain 纯函数，fs 读取只经 DocsReader 端口，
与本仓既有内容闸门（编号串联 / serves 孤儿）同款三层结构。

design→decomposing 转移共有**四条路径**，完整性闸门必须全部接线，缺一即成绕过口：

1. 会话弹框肯定项自动推进（AskConfirm.ts 推进块——**现状完全不过 assertArtifactGates**，本次补上）；
2. 看板产物确认后的自动推进（http/routers/requirements.ts handleArtifactConfirm 后段）；
3. 会话 reqboard_move（MoveRequirement.ts，现状走 assertArtifactGates）；
4. 看板移动端点（http/routers/requirements.ts 移动处理，现状走 assertArtifactGates）。

确认通道共**三条**（会话弹框 / 会话文字证据 / 看板一键），拆分内容扫描在三条落章前统一执行，
判定函数单点（domain），装配函数单点（content-gate-wiring），三条通道只调用不各自实现。

## 4. 规范层修复（serves: FR-4）

提示词片段与指南是 agent 的指令源，与代码矛盾即"提示词让写、代码不让交"（D1 实证）。
修正后必须重跑生成器并过字节级同步门禁（scripts/check-prompt-fragments.mjs），
防止片段源与 generated/fragments.ts 再次漂移。详见 backend.md §4。

## 5. 不改清单（serves: FR-6）

- 状态机与五道门结构（G0-G4）不动；只在 G2 门上加校验；
- decomposing 阶段的 plan_submit 既有门禁（编号串联 / serves / 文档集）行为不回退；
- 根级 design.md 的 notes 归类规则不动；拆分内容门禁只管 kind=design 产物（design/*.md）；
- 验收期 9 类文档口径（domain/workflow/DocCompleteness.ts）本需求不动，列为后续跟进；
- 会话侧查看器 absolute 地址兜底不做（用户 2026-09-21 弹框未选用，需求 §5.5）。
