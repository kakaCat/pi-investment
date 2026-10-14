# t-b52f3f 删 5 个孤儿的重复 provider·测试

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
删 5 个孤儿的重复 provider·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-01T11:00:57.695Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

测试段：四条验收全部达成——已删模块零引用、取数管理器正常、取数相关测试与删除前**逐字一致**（无新增失败）、保留文件仍可用。

### 完成项

- 验收①：对已删 5 个模块的引用 = **0**
- 验收②：`python -c "from adapters.outbound.datasources.manager import get_data_provider_manager"` 正常
- 验收③：`pytest tests/ -q -k "provider or datasource or financial"` → **15 failed / 534 passed**，与开工前基线（回退 5 个文件后跑的同一组）**逐字一致** ⇒ 删除引入 0 回归、0 新增失败
- 验收④：保留文件可用——`from application.services.financial_providers import EastmoneyDirectProvider, SinaWebFinancialProvider` 通过（联调段已一并验证真实取数调用）
- 局限（如实记录）：本子卡模板验收命令写的是 `pnpm test` / `npx tsc --noEmit`（TS 工具链），与本仓 Python 栈不匹配；已按等价的 pytest 基线与 import 实测执行，口径差异已在汇报中记明

---
