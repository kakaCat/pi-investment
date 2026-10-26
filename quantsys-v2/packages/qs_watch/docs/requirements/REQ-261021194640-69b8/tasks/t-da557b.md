# t-da557b 关闭待办接规则变更联动·研发

> 需求：REQ-261021194640-69b8 盯盘执行闭环三接缝：成交回写·消息投递·待办闭环

## 在做什么
关闭待办接规则变更联动·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-21T12:25:35.331Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

研发段完成：close 支持结构化 rule_change，联动先于收敛、失败留待办，路由与响应同步，新增 8 例测试。

### 完成项

- TodoService.close 新增 rule_change 入参：先落规则与审计、后收敛待办
- 新增领域错误 WatchTodoRuleChangeFailed（422 语义），未装配/缺溯源/非法动作统一走它
- 关闭路由透传 rule_change 并在响应 data 返回 rule_change 摘要
- 新增 8 例接线测试：正向、旧行为、仅 ignored、联动失败留待办、缺溯源、未装配、缺理由、重复关闭
- 顺带对齐端口与测试替身的 create 签名（evidence），合同测试恢复全绿

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/todo_service.py`
- `../../packages/qs_watch/qs_watch/domain/watch/ports.py`
- `../../adapters/inbound/fastapi_app/routes/watch_todo_async.py`
- `../../tests/application/test_watch_todo_close_rule_change.py`
- `../../tests/application/test_todo_service.py`

### 下一步

联调段：核对接线与错误码映射

---
