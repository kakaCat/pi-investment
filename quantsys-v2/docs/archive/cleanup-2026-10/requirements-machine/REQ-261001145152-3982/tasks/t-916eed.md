# t-916eed 删 5 个孤儿的重复 provider·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
删 5 个孤儿的重复 provider·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-01T10:50:59.799Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**把"同一个数据源在两层各写一份、但只有一层真的在跑"的清掉了 792 行**——application 层那 5 份同名财务取数实现删掉，实测取数的组装与结果都没变（前后测试结果逐字一致）；保留下来的两个文件因为仍被 adapters 树调用而原样留着。

### 完成项

- 核查确认这 5 个是**同名重复实现**：`tencent/akshare/sina/eastmoney/tushare_provider.py` 各定义一个与 `adapters/outbound/datasources/providers/financial/*` 同名的类，而 manager.py:104-106 实际装配的是 **adapters 树**那一套（实测装配结果：SinaFinancialProvider / EastmoneyFinancialProvider / AkshareFinancialStatementProvider）
- 零引用证据：5 个类名在 `financial_providers/` 目录外的使用数分别为 0 / 4 / 4 / 0 / 0——其中那个 4 是 adapters 树**自己同名类**的定义与使用，非对 application 层副本的引用
- 执行删除：5 个文件共 **792 行**（tencent 226 / akshare 124 / sina 132 / eastmoney 142 / tushare 168），并同步清理 `__init__.py` 的 5 条 import 与 `__all__` 条目（保留 base / eastmoney_direct / sina_web 三个）
- 验收②：`get_data_provider_manager` 正常，装配的仍是 adapters 树三个 provider
- 验收③（回退对照）：`pytest -k "provider or datasource or financial"` → 删除后 **15 failed / 534 passed**；把 5 个文件恢复后跑同一组 → **同样 15 failed / 534 passed** ⇒ 删除引入 **0** 回归
- 验收④：被保留的 `EastmoneyDirectProvider` / `SinaWebFinancialProvider` 仍可导入（adapters 树懒加载依赖它们）
- 验收①：已修订口径——对已删 5 个模块的引用 = **0**（原字面口径会把对保留文件的 2 处活代码懒加载也算进去，无法也不该达成）
- 过程纪律：本次先核查引用、再改 `__init__`、再删文件、后跑测试，并在删除前先验证包仍可导入（避免重演上一张卡"删完才发现漏了相对导入"）

### 改动文件

- `application/services/financial_providers/__init__.py`

---
