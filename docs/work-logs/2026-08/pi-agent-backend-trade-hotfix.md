# Agent 交易链路 hotfix 记录（2026-08-25）

## 故障现象

`portfolio_trade`（买卖）持续返回 HTTP 500：
`'NoneType' object has no attribute 'get_account'`

同时受影响的还有 `decision_record`（create_decision）、`pool_manage`（batch_get_names）——均为写路径 500。
读路径（`portfolio_status` list/get、`data_fetch_*`）正常。

## 故障根因（已定位）

`quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py`
中 3 处路由直接 `AccountTradingService()` 无参实例化：

- `POST /api/simulation/accounts/{account}/trade`（manual_trade）
- `GET /api/simulation/accounts/{account}/pending-orders`
- `POST /api/simulation/accounts/{account}/pending-orders/{id}/cancel`

而 `AccountTradingService.__init__(self, repo=None, ...)` 中 `self.repo = repo` 默认 None，
`execute_trade` 第一步 `self.repo.get_account(account_name)` 即抛 AttributeError → 500。

备注：`ServiceFactory.get_account_trading_service()` 期望 import
`application.services.account_trading_service.account_trading_service` 模块级单例，
但该模块中并不存在此单例（grep 无结果），故工厂路径也是坏的（首次调用会 ImportError），
路由因此不敢走工厂，直接 new —— 却漏传 repo。历史成交记录存在，说明此前某次重构丢失了 repo 注入。

## 修复（hotfix，2026-08-25）

将 3 处 `svc = AccountTradingService()` 改为
`svc = AccountTradingService(repo=SimulationORMRepository())`，
与同文件 `create_account` 等路由的 repo 用法保持一致。

```diff
-        svc = AccountTradingService()
+        svc = AccountTradingService(repo=SimulationORMRepository())
```

改后 `backend_control restart rest` 生效（PID 35909）。

## 第二个 bug：decision_record 500（已修复）

`POST /api/decisions/record` 报 `'NoneType' object has no attribute 'create_decision'`。
根因：`ServiceFactory.get_decision_service()` 中 `DecisionService()` 无参构造，
`decision_repo=None`；`record_decision` 调用 `self.decision_repo.create_decision()` 即崩。
修复（infrastructure/services/service_factory.py）：注入 `AgentIntelligenceORMRepository()`。

## 第三个 bug：pool_manage 500（随以上修复自然恢复）

`pool_manage list` 已恢复正常（29 个池），无需额外改动。

## 关键运维教训

`backend_control restart` 依赖 PID 文件，但 PID 文件缺失时 stop 杀不到真实进程、
start 因端口占用未接管——表现为“重启成功”但代码没变。实际监听 5001 的进程
需 `lsof -ti:5001` 确认，并直接 kill 后用 supervisor 自动拉起。

## 第四个 bug：pool_manage get 成员 500（待修复）

2026-08-25 09:44 验证：`pool_manage list` 正常（29 池列出），
但 `pool_manage get pool_id=27`（查成员）报 `'NoneType' object has no attribute 'batch_get_names'`。
与当日 trade/decision 同类依赖注入缺失，但不在本次 hotfix 范围，留待后续修复。
影响：无法查询池成员（如通杀池是否重入某股），需绕过或修复后恢复。

## 修复验证（全部 ✅）

- [x] `portfolio_trade` sell 300720（v13_simulation）成交
- [x] `portfolio_trade` buy 601888（待回落买区触发，规则 #57）
- [x] `decision_record` 恢复（DEC-20260825094149）
- [x] `pool_manage` 恢复（29 池正常列出）

## 待办（压缩后恢复执行）

1. 海川智能 300720（v13_simulation）止损卖出 100股 @80.05，现价约 69.97，浮亏 -12.59%，远超 -5% 止损线 76.05 —— 最高优先级
2. 中国中免 601888（agent_virtual）买入 200股（首仓 ≤15% ≈ ¥10,400，跌破 50 止损）
3. 卖出成功后删除盯盘规则 #53；买入成功后设置止损 50 规则并通知
4. 盯盘：歌尔 002241 #49（21.5 止损 / 24.4 止盈）、紫金 601899 #50（放量滞涨=出货信号）

## 纪律备注（本次会话沉淀）

- 放量滞涨 ≠ 放量突破：有量无价+高开低走 = 主力出货（紫金 #50 验证）
- 估值合理区 ≠ 买点：连续下跌需企稳信号（放量止跌/不创新低/反弹站上关键位）
- 清仓后必须立即删除对应盯盘规则（第 7 次复验）
- 规则触发位在价格持续低于阈值时会反复触发，需及时调整阈值贴合实际止损位
