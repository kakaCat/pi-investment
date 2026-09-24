# 评审报告 · REQ-260922182638-0777（实施方自评）

> 评审人：w-89aa3b25（investor，即实施窗口）｜ 日期：2026-09-22
> 性质：实施完成后的自评复核；正式验收以人工审核为准。

## 对照设计逐条复核

| 条款 | 设计承诺 | 落地核验 | 结论 |
|------|---------|---------|------|
| FR-1 | 六处映射表收敛为唯一事实源 | 新建 src/shared/artifact-labels.ts（KIND_LABELS/KIND_ICONS/DOC_FILE_LABELS + 3 函数）；stage-panel / artifacts / verification / toolviews(3) / render-summaries 全部改 import；grep 旧表名零命中；「需求文档」定义只剩该文件一处 | ✅ |
| FR-2 | 五区块术语一致、无英文裸显 | 归档区 requirement 由「需求说明」统一为「需求文档」（client-view.test 断言同步）；toolviews 补 design/decomposition/task_detail；render-summaries 的 plan 统一「拆分计划（旧版）」；未知值走中文兜底 | ✅ |
| FR-3 | 未知值中文兜底 + 防漂移 | artifactKindLabel 未知 → 「产物（mystery_kind）」，空串不 throw；docFileLabel 未知 → 「设计文档（foo.md）」；TC-001/TC-005 断言全部 ArtifactKind 已配中文名、effectiveDesignDocs 全部规范文件名 ∈ DOC_FILE_LABELS 键集 | ✅ |
| FR-4 | 文件名级中文化 | traceNodeLabel 对 design 多份改 docFileLabel：架构文档/数据模型/接口文档/测试用例/迁移方案/前端设计/后端设计/用例文档；按钮文字不再裸显文件名，data-path 与 title 保留完整路径 | ✅ |
| FR-5 | 节点文档全展示 | renderTraceChain 删「任务卡×N」折叠分支，逐张渲染 taskCardLabel(path, title)；新增 taskTitleByCardDoc(payload) 经 artifact.path ↔ StageTaskRef.cardDoc 精确匹配取名称，匹配不到降级「任务卡（t-xxx）」；缺失红字「（缺失）」分支不变 | ✅ |

## 发现与如实记录

1. **设计清单口径偏差（已自纠）**：requirement/design/interfaces.md 写「7 种 ArtifactKind + 4 种扩展」，实测枚举为 **9 值**（含 notes、task_output）——notes 原已配「其他」，task_output 此前无中文名。已在共享表现场补配「任务产物」并纳入 TC-001 护栏；测试文件与映射表同步按 9 值口径表述。
2. **全量回归 4 条红灯全部非本需求**（归因证据见 tests/evidence.md §4）：client-view 归档栏、repository ID 格式、layer-boundary(diag-log.ts)、size-budget(index.ts 416 行) —— 前三条为共享工作区另一窗口未提交改动（git status 实证 M board.ts / M CaptureRequirement.ts / M src/index.ts），且 process.chdir 一族在 --pool=forks 下即恢复（vitest workers 环境特征）。本需求**未**代为修改他人在途文件。
3. **顺带修正 2 条钉住旧行为的断言**（属预期行为变更，非放宽门禁）：acceptance-criteria 的「任务卡×」顺序断言、client-view 的归档区「需求说明」断言——两者断言的正是本需求要改掉的旧显示，改后与 FR-2/FR-5 一致。
4. **覆盖链路缺口（已修复，根因值得上游关注）**：批准计划后自动开跑因 `requirement_uncovered` 暂停——根因是**任务↔FR 绑定不落 TaskRecord**，只随 decomposition.md 的 RTM 覆盖表持久化；我最初手写的拆分计划任务表列名为 key/requirement_refs，RTM 解析器只认「任务编号 + 根编号」列，故落库后接收标记全红。补 RTM 覆盖表（12 条绑定）后 reqboard_status 显示 FR-1~5 全 done、unreceived=[]。**建议**：decompose 落库时自动把 refs 渲染成规范 RTM 表写回 decomposition.md，而非依赖计划作者手写列名（已 memory_write 留痕）。
5. **浏览器像素级核对**：本窗口无浏览器自动化通道，机器可核验项（构建产物内容 + 单测渲染断言）全部通过；prototype.html §1–§5 的逐项目视核对按流水线交给人工验收单。
