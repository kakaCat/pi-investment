# t-0efb76 端口与 DI 收敛·测试

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
端口与 DI 收敛·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-02T01:31:00.038Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

测试段：**验收三条都拿到了实测数字**——端口同名重复归零、生产代码里已无一处绕过唯一入口去取服务、测试除既有失败外零新增（那条看似新增的失败，回退我的改动后照样失败，已证明与本卡无关）。

### 完成项

- **验收①（端口同名去重）**：`comm -12 <(grep '^class I' repository_ports.py) <(grep '^class I' repository_ports_extended.py)` = **0** ✅
- **验收②（DI 入口收敛为 1 个）**：生产代码里 `EnhancedServiceFactory.resolve` 调用 **0** 个、`service_registry.create_*` 调用 **0** 个 ✅——唯一入口 = `ServiceFactory`（并已把 30 个生产文件迁到它）
- **验收③（测试基线不退化）**：三层（domain/application/infrastructure）跑出 **16** 条失败/错误；其中 `tests/application/test_trade_input_type_guard.py::test_amount_string_parsed` 经**回退对照**证明**回退我这批改动后同样失败**（回退后仍 16 条、含同一条）→ 属既有问题，**本卡零新增**
- **收集数**：**6401**（相较改动前的 6435，差值 = 本卡删除的 2 个 DI 死件测试文件的用例数，属预期）
- **口径说明**：子卡模板写的是 `pnpm test` / `npx tsc --noEmit`（TS 工具链），与本仓 Python 栈不匹配，已按等价 pytest 命令执行并记录
- **本卡未做的部分（如实留档、不属验收标准）**：卡面「实施方案」③「87 处直连 `adapters.outbound.repositories` 改走端口」——实测是**逐点架构改动**（每处要把 `XORMRepository()` 换成经端口注入），且 87 处的分布已勘查留档（Top: analysis_jobs 10 / daily_orchestrator 8 / watch_loop_wiring 6 …；主仓储都已有端口）。建议单独开卡分文件推进

---
