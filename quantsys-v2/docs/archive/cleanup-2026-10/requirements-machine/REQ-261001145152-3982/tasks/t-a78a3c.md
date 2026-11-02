# t-a78a3c 数据访问规则收口 + provider 归位·联调

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
数据访问规则收口 + provider 归位·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-01T12:40:52.246Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：两处改动都**真跑了一遍**——指数基准能取到 6003 条真实数据（末条正是我们补回的 09-30），行业截面仍返回**49 条**、与改造前口径完全一致，风格检测端到端可用且非降级；说明这次是"换了取数出口、没换数据"。

### 完成项

- 联调①（指数路径）：`get_data_provider_manager().get_index_daily('sh000300')` 实测 **success=True、source=akshare、6003 条记录**（2002-01-04 ~ **2026-09-30**）——`risk_lens` 的 β/α 有真实基准可用，且末条正是本需求此前补回的 09-30
- 联调②（行业截面，**口径未变的硬证据**）：`fetch_sina_sector_boards()` 真实调用返回 **49 条**，样例 `{'name': '玻璃行业', 'change_pct': 0.0062910886728949}` —— 与改造前"新浪 49 行业"契约完全一致（证明复用 adapters 既有实现没有换数据源/换口径）
- 联调③（端到端）：`MarketStyleDetector().detect_market_style()` 正常返回（style=value、confidence=0.9039、`degraded=False`），日志显示 `source='sina_sector_spot(实时回退, DB无真实行)'` —— 即新路径确实被走到且结果可用
- 联调④：两处改动都保留了**显式降级**语义（基准不可用 → `benchmark_note` 写明原因；截面失败 → 返回 None 由调用方回退），未出现"静默返回空/编造数据"
- 联调⑤：`tests/services/test_market_style_detector.py` + `tests/services/test_market_data_index_history.py` = **15 passed**
- 局限（如实记录）：本子卡模板验收命令写的是 `npx vitest run`（TS 工具链），与本仓 Python 栈不匹配；已按真实调用 + pytest 执行

---
