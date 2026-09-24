# t-1adbb0 迁移与兼容：FR-1 回归、回滚演练、旧渲染兼容、运维指引

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
迁移与兼容：FR-1 回归、回滚演练、旧渲染兼容、运维指引

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
执行回滚演练通过：UPDATE 改回 …172829 后 curl 发测试消息落原群、再改回 …60d879 落盯盘群（投递日志 status=sent 与群可见一致）；pytest 兼容用例通过（无 watch_level 仍旧渲染）；ops-note.md 落盘且步骤可复制执行

## 实施方案（implementation）
①psql 断言脚本（含回滚 SQL）；②兼容用例：不带 watch_level 的 WatchTriggered 仍旧渲染；③docs/requirements/REQ-260924104605-ad0a/ops-note.md 写渠道表改法与回滚步骤

## 上游产出摘要（dependsSummary）
- 重写四级模板为意图驱动骨架（判重/多账户/名称优先/卫生）
- 接线 direct 渠道路由与回执 os_channel、补 rule_id 传递
- 回执聚合投递 + 名称批量解析 + 时间格式修复
- 处置结论回执：close 触发 result + 三要素文案 + 响应填充

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-24T05:37:21.593Z，窗口 session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9）

迁移与兼容收尾：渠道表回归断言钉死（10 行盯盘群/3 行原群，错一行即报警）；回滚演练真实跑通——改回原群 webhook 发探针落原群（status=sent）、改回盯盘群再发落盯盘群，演练前后断言均 OK；补了旧渲染兼容回归（无级别的存量通知仍走老格式，七段结构完整）；运维指引落盘，换群/回滚/排障三步可复制，其中 SQL 已用事务回滚法验证可执行。

### 完成项

- FR-1 回归断言脚本 scripts/watch-channel-drill.sh（assert/rollback/restore/probe 四命令）
- 回滚演练执行通过：探针 ef464627 落原群（…172829 sent）→ 恢复后探针 e8a7c137 落盯盘群（…60d879 sent）→ assert 回到新映射
- 兼容回归 tests/notification/test_legacy_render_compat.py 5 例（无 watch_level 仍旧渲染）
- ops-note.md 落盘（映射表/日常体检/换群/回滚/排障），文中 SQL 经事务回滚验证可执行
- 演练中修复 macOS bash 3.2 UTF-8 变量名解析坑（${var} 花括号）并已注释进脚本
- 回归 85 例全绿（notification+watch）

### 改动文件

- `quantsys-v2/tests/notification/test_legacy_render_compat.py`
- `agent-dh/docs/requirements/REQ-260924104605-ad0a/scripts/watch-channel-drill.sh`
- `agent-dh/docs/requirements/REQ-260924104605-ad0a/ops-note.md`

### 下一步

t7 端到端联调（合并回主线 + 服务重启后五步验证）

---
