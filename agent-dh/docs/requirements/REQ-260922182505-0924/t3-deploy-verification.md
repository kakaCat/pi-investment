# t3 部署后独立验证 · REQ-260922182505-0924

> 验证时点：2026-09-22T12:31:08.882Z｜验证实例：独立调试实例 :13081（新代码，不影响现役 :13080）

## ① 独立回归复核（非修复卡自证）
`npx vitest run packages/web/dsh-pmboard` 失败集 = 86 条，与 t1 基线（86 条）**差集为空**（无新增、无消失）。清单：t3-independent-failures.txt

## ② triage 路由 404（新代码实例实测）
- GET  /dashboard/api/reqboard/triage        → 404 {"success":false,"error":"未知路由：GET /dashboard/api/reqboard/triage","code":"not_found"}
- POST /dashboard/api/reqboard/triage/confirm → 404 not_found
- POST /dashboard/api/reqboard/triage/rebind  → 404 not_found
- POST /dashboard/api/reqboard/triage/reject  → 404 not_found
（返回既有的"未知路由"404 信封，无新错误码——与 interfaces.md 设计一致）

## ③ 看板正常渲染、无 triage 视图入口
- 看板状态接口 GET /dashboard/api/reqboard/ → 200（正常服务）
- 客户端产物 lib/client.js 经 verify-client-build 校验通过；grep "dsh-pm-triage|buildTriage|fetchTriage|triage-confirm" 命中 0 处（面板与入口不存在）
- 服务端产物 dist/index.mjs 同样 0 处 triage 引用
- 页面级行为与现役实例逐点一致（/ → 401 需认证、/dashboard → 404 两实例同款，证明 404 是既有路由布局而非本次改动引入）
- ⚠️ 浏览器人工目测无法由 agent 执行：上述为可机器验证的等价证据；最终目测请在验收时打开看板确认（验收单已列此项）

## ④ migration v4 fixture 保持绿
`npx vitest run packages/web/dsh-pmboard/tests/migration.test.ts` → Test Files 1 passed、Tests 9 passed（老台账照常加载的锁定证据）

## 部署方式说明
现役 :13080 由 launchd 托管且运行本会话，未对其执行重启（避免自杀式中断）；验证在 :13081 独立实例完成。
新代码随下次 launchd 重启（kickstart）自然生效；如需立即生效可执行 `agent-dh/scripts/restart-with-build.sh`。
调试实例已停机（stop.sh 13081），pidfile 已恢复指向 :13080（pid 60994）。
