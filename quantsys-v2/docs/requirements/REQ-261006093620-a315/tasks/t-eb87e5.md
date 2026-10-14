# t-eb87e5 判据真源：trading_day_gate 模块与策略入口·复核

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
判据真源：trading_day_gate 模块与策略入口·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T01:51:43.325Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

复核段完成：契约与设计逐字一致；差分核对证明新旧实现 7 场景 × 3 入口输出完全相同，搬迁无行为漂移。

### 完成项

- 契约核对：4 个函数签名与 design/interfaces.md §1 逐字一致
- 常量核对：三值策略、KNOWN_POLICIES、SOURCE_GATE_ERROR 与设计一致
- 差分核对：7 个场景 × 3 个入口，新旧实现输出逐字相同（含判定器异常路径）
- 差分脚本落盘为可复核产物 notes/gate-differential-check.py，退出码 0
- compileall 通过；AST 依赖扫描确认无 infrastructure 反向依赖
- 如实记录：venv 未装 ruff/black，本仓 lint 门此次未跑
- 对照设计逐条核对结论：无偏离

### 改动文件

- `docs/requirements/REQ-261006093620-a315/notes/gate-differential-check.py`

### 下一步

测试段：跑本卡验收命令与相邻回归，并把读数留档。

---
