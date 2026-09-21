---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3
---

# 前端实施设计（REQ-2d1c74）

## 1. 呈现层数据契约（serves: FR-1, FR-2）

本需求不重设计节点详情页信息架构（需求 §5.4），只让既有"设计文档交付状态"跟上新文档集：

- `application/internal/design-docs.ts` 的 `designDocStatus()` 扩展：输出条目增加
  条件必交文档与豁免标记——`{ name, path, submitted, conditional?: 'frontend'|'backend', exempted?: string }`，
  策略来源 = host 侧读 requirement.md front-matter（designDocPolicyFrom），client 不碰 fs。
- `shared/protocol.ts` 的 `DesignDocStatus` DTO 同步扩两个可选字段（向后兼容）。
- design-docs.ts 头注"不参与任何闸门"随 FR-2 作废：呈现与闸门共用同一份策略解析结果，
  页面上"已交/未交"与 G2 拦截清单天然一致。

## 2. 看板交互（serves: FR-2, FR-3）

- `client/stage-panel.ts`（现 244 行直接读 delta.requiredDesignDocs）改读 host 投影的
  DesignDocStatus 全量条目：条件必交文档带"条件"徽标，豁免项带豁免理由灰显；
  未交项在 G2 被拒时与服务端 gaps 清单一一对应标红。
- 确认按钮语义变化：kind=design 的"一键确认"= 成组确认全部设计文档，按钮悬停文案写明
  "将确认全部 N 份设计文档"；被拒（design_doc_incomplete / design_contains_decomposition）时
  复用既有错误展示通道，消息直接呈现缺口清单。
- 无新增页面、无新增路由；改动限 stage-panel 的条目渲染与确认按钮文案。
