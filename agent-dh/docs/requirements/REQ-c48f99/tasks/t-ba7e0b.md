# t-ba7e0b 指南文档：工具 render 人话首行约定

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
指南文档：工具 render 人话首行约定

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
docs/guides/tool-render-human-summary.md 落盘；grep 命中 docs/README.md 含该文件链接

## 实施方案（implementation）
新文档 + docs/README.md 加索引行

## 上游产出摘要（dependsSummary）
- renderSmart 人话首行：13 个 pmboard 工具逐配 summarize

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T03:36:40.148Z，窗口 session-85447f15-ee57-44ef-8fd0-d8526111c0b3）

指南落盘：docs/guides/tool-render-human-summary.md（renderSmart 约定：首行中文摘要单行 ≤120 字符 + 空行 + JSON 明细；summarize 五条契约；卫生门禁配合；39 处插件 render 的跟进路径），已挂 docs/README.md 卷 3 索引

### 完成项

- docs/guides/tool-render-human-summary.md 落盘
- docs/README.md 卷 3「工具与协议」挂索引链接（grep 命中 1 处）

### 改动文件

- `docs/guides/tool-render-human-summary.md`
- `docs/README.md`

### 下一步

t5/t6 实测验收

---
