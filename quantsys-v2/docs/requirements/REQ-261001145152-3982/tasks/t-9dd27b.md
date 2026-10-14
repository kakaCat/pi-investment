# t-9dd27b 删重复实现（零引用项）·联调

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
删重复实现（零引用项）·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-01T10:13:40.305Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：删除后的代码在**全新进程**里加载并正常提供数据，两条导入链与其业务消费方全部走通；期间服务真的挂过一次（后台作业被回收），探针当场报警、重启后恢复——顺带证明了探针不是摆设。

### 完成项

- 联调①（最强证据）：**全新进程**加载删除后的代码并正常服务——/docs 200、health 200、/api/charts/kline 返回 09-30 数据（覆盖静态导入与懒加载两条路径）
- 联调②：删除涉及的两条导入链在进程外全部走通——adapters 转发壳 8 个符号齐备（get_factor_adapter/get_adapter/AkShare/EastMoney/Sina/BaseMarketAdapter 等）、core 公共 API 齐备（含 pipeline 与已改指 domain 的 base_calculator/exceptions）、本次修过相对导入的 data_validator 可导入
- 联调③：直接消费该转发壳的业务方均可导入——factor_layering_service、opportunity_scoring_service、infrastructure.di.container（真实符号是 Container / get_container()）
- 联调④（意外但重要，属真实故障而非构造）：本卡进行中服务曾整体不可用（端口无监听、探针 exit 2 报警、日志最后一条仍是正常 200 → 进程被外部回收而非崩溃），根因是**本会话后台作业注册表被清空、连带回收了子进程**；已重启服务并复查 /docs 200、探针 exit 0、四路调度仍全关。这既是"后台进程不留存"这一已知限制的实证，也是**探针第一次真实抓到故障**（此前只做过注入验证）
- 联调⑤：自我纠错——首版我臆造了 `DIContainer` 这个符号名导致 ImportError，实为 `Container`；模块本身导入一直是成功的。已按真实符号复测通过
- 局限（如实记录）：本子卡模板里的验收命令指向 `npx vitest run`（TS 工具链），与本仓 Python 栈不匹配，故按 pytest 与 import 实测执行

---
