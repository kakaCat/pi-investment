# t-e2ccda 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·联调

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

## 汇报 1（2026-09-27T10:35:50.004Z，窗口 43eb176c-d21f-451b-a75f-cf3621c17f63）

reqboard_task_status 接口联调（真适配器 + 真磁盘台账）：新增 tests/task-status-integration.test.ts，请求样例与期望响应逐字段比对一致，并证明读数来自持久化台账而非任务卡文档。

### 完成项

- 联调请求采样：reqboard_task_status({task_id}) 读真 JsonLedgerRepository 的 dsh-reqboard.json
- TC-I1 写→读闭环：真 reqboard_task_report 落盘 lastReport → status 工具原样读回（report 三字段与磁盘一致）
- TC-I2 逐字段比对：台账持久化 lastRun/lastReport → 返回 run/report/workflow 与期望对象**完全相等**
- TC-I3 数据源证明：磁盘无任何任务卡文档（docs/.../tasks/*.md 不存在）时读数仍成立——旧 fs 直读路径此时必空
- 回归：相关 5 个套件 76/76 通过；tsc --noEmit 对本次改动文件 0 错误

### 改动文件

- `packages/web/dsh-pmboard/tests/task-status-integration.test.ts`
- `packages/web/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts`

### 下一步

复核阶段：独立核对接口契约与台账口径一致性（review 子卡 t-ebe92d）。

---
