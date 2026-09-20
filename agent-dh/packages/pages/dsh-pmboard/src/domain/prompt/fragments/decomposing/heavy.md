# 拆分（decomposing）· 完整档

> **本仓口径例外**：superpowers 14 份 vendor 原文里**没有**"拆分 / 任务 DAG / 卡质量"的对应
> skill（对照结论 §4.5），故本档为**自写完整档**，不做"与 vendor 原文逐字一致"断言。
> 可迁移要点三条（来自 writing-plans 的通用纪律）：文件结构先定、任务右尺寸、
> 每张卡独立可测。

## 1. 代码层面变更盘点（对照需求文档 + 设计一套）

- [ ] **新增**：哪些接口 / 功能 / 文件。
- [ ] **修改**：精确到模块 / 函数。
- [ ] **删除**：哪些旧符号 / 旧路径。
- [ ] 写进 docs/requirements/REQ-xxxxxx/decomposition.md。

## 2. 批次与依赖（depends_on）

- [ ] 按依赖安全序排批次：被依赖者先定义，**禁止前向引用**（引用后定义的任务会在提交时被打回）。
- [ ] depends_on 用批次内 key 引用同批任务；跨批用已落库任务 id。

## 3. 每卡必给 implementation 与 acceptance

- [ ] 做什么（title / description）＋ 怎么做（implementation：改哪些文件 / 步骤 / 验证方式）
      ＋ 怎么算完（可证伪 acceptance）＋ 依赖。
- [ ] **薄卡拒落**：缺 implementation、或 acceptance 是空话（"功能正常""优化体验"）
      会被代码级拒绝。

## 4. 边界校验（不超范围、卡可独立验收）

- [ ] 每张卡都能被独立验收：一个新窗口**零会话历史**、只凭任务卡就能开工。
- [ ] 本阶段不二次创作设计：与设计矛盾时**退回设计改计划**
      （重新 `reqboard_submit(kind=plan)` 并重新批准），不在拆分阶段私改设计。

## 5. 提交与批准门（2026-09-21：拆分计划在拆分阶段写）

- [ ] `reqboard_submit(kind=plan)` 提交拆分计划（path=decomposition.md、summary、tasks=任务表）。
- [ ] `reqboard_ask_confirm(target=plan)` 弹框请人批准——**批准后自动落库任务卡并进入实施**
      （中途不再打断）；未获批准 reqboard_decompose 被代码级拒绝。
- [ ] 兜底：计划未含任务表时，`reqboard_decompose` **必须传 tasks**——本工具即任务卡创作口。

## 6. 交棒

- [ ] 下一步：implementing —— 用 reqboard_ask_confirm(target=plan) 交棒；未获批准不得进入。
