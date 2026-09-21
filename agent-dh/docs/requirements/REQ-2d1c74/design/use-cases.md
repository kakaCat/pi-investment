---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3, FR-5, FR-6
---

# 用例文档（REQ-2d1c74）

## 1. UC-1 文档集未交齐，G2 拦截（serves: FR-1, FR-2）

feature 需求只交了 architecture/data-model/interfaces/test-cases 四份（缺 use-cases.md），
agent 调 reqboard_ask_confirm(kind=design) 或 reqboard_move(decomposing)。
**期望**：确认/推进被拒，返回 design_doc_incomplete，消息列出 `design/use-cases.md 未交`；
看板确认与移动端点同样被拒。交齐后重试放行。

## 2. UC-2 端侧条件与豁免（serves: FR-1）

需求 front-matter 声明 `sides: frontend` → frontend.md 变必交、backend.md 不要求；
声明 `design_exempt: use-cases.md=无用户交互场景` → 该份豁免生效。
**期望**：缺 frontend.md 被拒；豁免项不出现在缺失清单；豁免键拼错/理由为空 = 不生效并提示。

## 3. UC-3 设计文档混入拆分内容，确认被拒（serves: FR-3）

某份 design/*.md 里出现带 depends_on 表头的表格。
**期望**：三条确认通道（弹框 / 文字证据 / 看板一键）均在落章前被拒，返回
design_contains_decomposition，消息指出命中文件与特征，并指引"把该内容挪到拆分阶段"；
代码块内的示例表格不误伤。

## 4. UC-4 成组确认（serves: FR-2）

设计文档共 5 份全部交齐，用户点一次确认。
**期望**：5 份产物全部落 confirmedAt；此后若目录里新增一份 design 文档（自动发现），
该份无确认章 → G2 重新拦截，消息列出未确认的那份。

## 5. UC-5 登记不存在的路径，当场被拒（serves: FR-5）

agent 调 reqboard_submit 时 path 写错（文件未落盘），或给出 brace 写法伪路径。
**期望**：登记即拒（不再等用户"点看才发现"）：不存在 → REQBOARD_FILE_MISSING，
伪路径/越界 → REQBOARD_ARTIFACT_NOT_OPENABLE，消息含 normalized 路径与原因；
看板自动发现入口登记的文件同样过形态校验。

## 6. UC-6 存量与回归（serves: FR-6）

isLegacy 存量需求（无 artifacts）走旧路径全放行；decomposing 阶段 plan_submit 的
编号串联/serves/文档集门禁行为不变；dsh-pmboard 全部既有测试保持绿。
**期望**：无历史需求被新闸门锁死；在途 feature 需求可用 design_exempt 声明过渡。
