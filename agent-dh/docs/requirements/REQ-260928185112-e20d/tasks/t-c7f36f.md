# t-c7f36f 迁移清单收口（其余 4 页）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
迁移清单收口（其余 4 页）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

## 实施方案（implementation）
把 design/migration.md 的面板清单固化为可排期清单 docs/requirements/REQ-260928185112-e20d/migration-checklist.md，每项五列（现有入口 / 依赖属性 / 关联 CSS / 改造工作量 / 风险），文末写明与需求文档“8 个面板 / 其余 7 个”的差异：实测 5 个页面包、待迁 4 项，并附实测命令；若需更正 requirement.md 措辞，走 reqboard_submit(kind=requirement, change_note=...)。

## 上游产出摘要（dependsSummary）
- 行为等价验证（含 E2E）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
