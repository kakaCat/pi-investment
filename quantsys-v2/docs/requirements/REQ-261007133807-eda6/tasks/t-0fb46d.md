# t-0fb46d 卡面「升级原因」行（旧渲染 + 分级渲染两条路径）·研发

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
卡面「升级原因」行（旧渲染 + 分级渲染两条路径）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-07T11:12:51.190Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t9 研发段完成：两条渲染路径各加「升级原因」行，6 条用例通过。

### 完成项

- 分级路径：WatchCardItem 增两字段 + _escalation_line + _skeleton_lines 插在「处置」与「下一步」之间
- 旧渲染路径：escalation_reason_line 模块函数 + 同位置插入
- 两条路径同形由同一组用例对拍（同一组变量 → 行逐字相同）
- 三种形态：码+理由 / 只有码 / 都没有（不渲染）；未收录码显示码本身
- 6 条用例通过

### 改动文件

- `infrastructure/notification/formatters/watch_level_templates.py`
- `infrastructure/notification/formatters/feishu_formatters.py`
- `tests/notification/test_watch_escalation_reason_line.py`

### 下一步

联调段：通知目录全套回归。

---
