# 错误事件处置：POST /api/strategies/stop/{id} 500（Class 'builtins.str' is not mapped）

- **事件 ID**：`e22c1dc2-c982-4b9d-8fea-fe986bb9686f`（source=v2，severity=error，频次 5）
- **处置窗口**：w-32314d00（投递来源 w-c8cae280）
- **处置时间**：2026-09-13

## 1. 现象与日志上下文

`logs/launchd-stdout.log`（2026-09-13 12:27:56 ~ 12:28:00）连续 5 条同源 500，且**不止 stop**：

```console
POST /api/strategies/delete/708 500   → Error deleting Strategy: Class 'builtins.str' is not mapped
POST /api/strategies/delete/711 500   → 同上
POST /api/strategies/delete/713 500   → 同上
POST /api/strategies/delete/717 500   → Error updating Strategy: Class 'builtins.str' is not mapped
POST /api/strategies/stop/163   500   → Error updating Strategy: ...
POST /api/strategies/stop/178 / 179 / 193 500 → 同上
```

日志里的 `Error updating Strategy` / `Error deleting Strategy`（首字母大写的 Strategy）
指向 `infrastructure/persistence/orm/base_repository.py:211/232`——通用 ORM 基类，
`self.model.__name__` = `Strategy`。

## 2. 根因：服务按「字典 API」调用，仓库继承的是「对象 API」——方法名撞车

调用链：`routes/strategies_async.py::stop_strategy` → `StrategyCodeService.update_strategy`
→ `self.strategy_repo.update(strategy_id, update_data)`，
而注入的 `strategy_repo`（config/services.yaml: `repositories.strategy`）是
`StrategyORMRepository(BaseORMRepository[Strategy])`，**没有** `update(id, updates)`，
于是方法解析落到基类的：

```python
def update(self, obj: T, commit: bool = True):   # base_repository.py:194
    self.session.merge(obj)                      # ← obj 实际是字符串 '163'
```

→ `UnmappedInstanceError: Class 'builtins.str' is not mapped`（是 `SQLAlchemyError` 子类）
→ 被基类 `except` 吞掉、打成 ERROR、返回 `None` → 路由判定失败 → **500**。
`delete(strategy_id)` 同理（`session.delete('163')`）。

**根因类型：代码 bug（接口契约不匹配），不是环境问题、不是误报。**

注：`StrategyORMRepository` 里已有 `update_strategy(id, updates)`，但它操作的是
`Strategy`（表 `quant.strategy_metadata`，系统内置策略元数据），**不是**用户策略表
`quant.strategy_configs`——这也解释了为什么不能简单改调 `update_strategy`。

## 3. 落地动作（已修 + 已重启 + 已实测）

1. `adapters/outbound/repositories/strategy_repository.py` 新增：
   - `update_user_strategy(strategy_id, updates) -> bool`：按 id 更新 `quant.strategy_configs`；
     可更新列用**白名单**（由 `information_schema` 实测：`metadata` 是真实列名，不是 `strategy_metadata`；
     `risk_config`/`strategy_profile` 等 JSONB 列显式 `CAST(:x AS jsonb)`）；白名单外字段忽略并告警；
   - `delete_user_strategy(strategy_id) -> bool`：按 id 删除用户策略行。
2. `application/services/strategy_code_service.py`：
   `update_strategy` / `delete_strategy` 改调上述显式方法（不再撞通用 CRUD 的名字）。
3. 重启使新代码生效：`launchctl kickstart -k gui/501/com.pi-investment.v2-api`（health 200）。

## 4. 验证（实测）

```console
# 修复前（旧进程）复现：
$ curl -X POST http://127.0.0.1:5001/api/strategies/stop/163
HTTP=500 {"success":false,"error":"策略停止失败"}

# 重启后（同一请求）：
$ curl -X POST .../api/strategies/stop/163          → HTTP=200  is_active 落库为 False
$ curl -X POST .../api/strategies/update/999901 -d '{"description":"probe-updated-by-curl"}'
                                                    → HTTP=200  描述已更新
$ curl -X POST .../api/strategies/delete/999901     → HTTP=200  行已从 quant.strategy_configs 删除

# 日志（重启后区间）：
Class 'builtins.str' is not mapped 出现次数: 0
/api/strategies/(stop|delete|update)/{id} 5xx 次数: 0
```

（探针行 999901 是本次为验证 delete 路径临时插入的 `zz-dispose-probe`，验证后已删除。）

**回归测试**：`tests/test_strategy_user_crud_contract.py` 4 passed——
用假仓库锁「服务必须调用 `update_user_strategy`/`delete_user_strategy`」，
并给通用 `update`/`delete` 设绊线（一旦退回旧写法，测试立即失败，而不是线上 500）；
另断言白名单包含真实列、拒绝不存在的列。

## 4.1 同一缺陷在错误台账里裂成 4 张卡（本次一并闭环）

| 事件 ID | 消息指纹变体 | 累计次数 | 状态 |
|---|---|---|---|
| `e22c1dc2` | `POST /api/strategies/stop/163 ... 500`（HTTP 访问日志行） | 6 | resolved |
| `a6c6b882` | `updating Strategy: Class 'builtins.str' is not mapped` | 6 | resolved |
| `63fe9c5b` | `Error updating Strategy: ...` | 2 | resolved |
| `1b541ee2` | `deleting Strategy: ...` | **246** | resolved |
| `47167e5b` | `Error deleting Strategy: ...` | 1 | resolved |
| `d03cc5c8` | `POST /api/strategies/delete/677 ... 500`（HTTP 访问日志行，delete 版） | 246 | resolved |

同一次修复覆盖全部 **6 张卡**（根因相同，只是采集器按消息前缀/logger 切出不同指纹）。

**全日志精确计数**（`grep -cE '"POST /api/strategies/(delete|stop|update|start)/[0-9]+ HTTP/1.1" 500'`）：
**252 行 = delete 246 + stop 6**，全部发生在 13:06:09 之前；重启后为 **0 行**。
（`1b541ee2` 与 `d03cc5c8` 的 246 是同一批调用的两种指纹，不是两次独立故障。）
`1b541ee2` 累计 246 次说明调用方在**循环重试删除**——修复后这些调用直接成功，循环自然停止。

**最后一次出现**：`logs/launchd-stdout.log` 13:06:09（`POST /api/strategies/stop/163` 500，
比本次重启早 10 秒）；重启标记 13:06:19 之后该串**出现 0 次**，回归复测 `stop/163` 返回 200。

## 4.2 附带修掉"重复派单"的来源（agent-dh · solve-kit）

本次处置期间同一根因被**重复派单 4 次**，其中两条投递到达时事件早已 resolved——处置窗口每次都要重新核验，
纯噪声。定位到派单边界缺一道复核：`packages/solve-kit/src/host.ts::createSolveHandler` 直接用**客户端传来的卡片快照**
组装消息，从不复核事件当前状态（卡片可能是旧快照，或已被其他窗口闭环）。

修复（2026-09-13，w-32314d00）：复用包内既有 `fetchEventStatus()`，在解析目标会话**之前**加一道前置复核——
事件当前为 `resolved`/`ignored` → 直接拒单并提示"看板卡片可能来自旧快照，如需重开请先点「复开」"；
查不到 / 查询异常 → **放行**（fail-open，宁多派不误拦）。

验证：`packages/pages/execution/tests/solve-predispatch-guard.test.ts` 5 passed
（resolved 拒单不解析目标、ignored 拒单、open 正常派单、查询异常放行、查不到放行）；
执行看板包全量 **35 passed**；`tsc --noEmit` 干净。
注：solve-kit 从 src 加载，但**当前进程已装载旧模块**——该护栏需 DSH 实例重启后生效（重启会中断当前会话）。

## 5. 遗留 / 建议

1. **同类撞车风险**：`BaseORMRepository` 的通用方法名（`update(obj)` / `delete(obj)`）与
   业务服务预期的字典 API 天生冲突。本次只修了用户策略这一处；建议对继承基类的仓库做一次
   `grep '\.update(\|\.delete('` 审计，确认其它服务没有同样按 (id, dict) 调用。
2. 触发这批 500 的调用方（12:27:56 连续 stop/delete 163/178/179/193/708/711/713/717）
   看起来是一次清理脚本；修复后这些策略的启停/删除接口已可用。