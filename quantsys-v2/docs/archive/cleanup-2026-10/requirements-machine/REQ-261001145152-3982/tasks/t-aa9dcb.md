# t-aa9dcb 删 5 个孤儿的重复 provider·联调

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
删 5 个孤儿的重复 provider·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-01T10:54:41.209Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：删除后取数链路**真跑了一次**——财务数据的组装与真实查询都正常返回（含标准结果结构），保留文件被调用的那两处懒加载路径确认是活代码。

### 完成项

- 联调①：`get_data_provider_manager()` 正常，装配的财务 provider 为 adapters 树的 `SinaFinancialProvider` / `EastmoneyFinancialProvider` / `AkshareFinancialStatementProvider`，报表 provider 为 `AkshareFinancialStatementProvider`——与删除前一致
- 联调②：**真实取数调用端到端通过**——`m.get_financial('600519','latest')` 返回非空 dict，含标准结构（success / data / source / attempted_sources / empty_sources / provider_errors），证明完整 provider 链（含保留文件的懒加载分支）未受删除影响
- 联调③：确认保留文件的两处懒加载是**活路径**（adapters/.../financial/eastmoney.py:33 与 sina.py:33 在函数内 import `EastmoneyDirectProvider` / `SinaWebFinancialProvider`）——这正是不能把"引用数归零"当验收口径的原因
- 过程留痕（运维侧，如实记录）：服务在本卡期间又被外部优雅关闭一次（日志 `Application shutdown complete`，非崩溃）；`nohup` 也逃不出作业回收，已改用**双 fork + setsid 脱离会话**方式启动（验证：ppid=1、独立会话），当前 /docs 200、探针 exit 0、四路调度仍全关。彻底解法仍是装 launchd（模板已就绪、未安装）

---
