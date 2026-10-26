# t-eb06ad 关闭待办接规则变更联动·测试

> 需求：REQ-261021194640-69b8 盯盘执行闭环三接缝：成交回写·消息投递·待办闭环

## 在做什么
关闭待办接规则变更联动·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-21T12:26:13.665Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试段通过：验收 64 例与合同/仓储回归 40 例全绿，无新增失败。

### 完成项

- 验收读数：test_rule_change_linkage + test_watch_todo_close_rule_change → 64 passed
- 合同与仓储回归：test_todo_service + test_watch_todo_repository → 40 passed
- 失败数 0；既有 2 例 watch_t12 基线失败与本卡无关（未触碰）

### 改动文件

- `../../tests/application/test_watch_todo_close_rule_change.py`
- `../../tests/application/test_todo_service.py`

### 下一步

父卡收尾后进入 sla-deadline：执行期限巡检与时区归一

---
