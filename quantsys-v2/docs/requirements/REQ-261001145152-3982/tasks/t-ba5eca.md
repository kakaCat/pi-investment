# t-ba5eca 端口与 DI 收敛·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
端口与 DI 收敛·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-02T01:10:52.683Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**"4 套 DI 入口并存"这件事查清并收敛了**——实测它不是四套平行入口，而是"1 个入口 + 2 个内部实现层 + 1 个死件"（死件连它的幽灵依赖一起删了）；同时把 30 个生产文件从"直连内部层"改成"只走唯一入口"、把两个端口文件里的同名接口合并成一处权威定义。过程中我自己三次把语义改坏（返回 None、顺手自动注册、改坏测试的安全包装），都靠回退对照查出来并修回原语义。

### 完成项

- **先做只读影响面勘查**（并按约定先给结论再动手）：7 个同名端口 → 实测**不是同一份**（B 里 6 个是各 1 方法的桩）；DI 四套 → 实测是 **1 入口 + 2 内部层 + 1 死件**（`service_factory` 本来就在调用另两层，不是平行实现）；87 处直连仓储 → 主仓储**都已有端口**，属机械替换但面宽
- **端口去重**：B 里 6 个桩改为从 A 转发；B 里那个与 A 同名但不同物的孤儿接口（`ISchedulerRepository`，实为 `AutomationTaskRepository`）删除；A 版仍是唯一权威。验证：7 个名字无论从哪条路径导入都指向同一处定义，全仓每名只剩一个 `class`
- **删 DI 死件**：`infrastructure/di/`（4 文件 / 253 行）经核实**生产零引用**（仅 2 个测试用）→ 删除，连它带出的幽灵依赖 `dependency-injector` 一并移除
- **DI 入口收敛（批次1）**：30 个生产文件由 `EnhancedServiceFactory.resolve` 改走唯一入口 `ServiceFactory.resolve`（它们本就都是函数内惰性导入，且内部三类 API `register/is_registered/...` **只有层文件自己用**）
- **自查出并修掉自己 3 处"改完看着对、其实静默变味"**：① 入口 resolve 初版**返回 None**（把静默降级引入 30 个调用方）→ 改为与内部层**逐字同语义**（未注册抛 ValueError）；② 初版还会**自动注册**、改变全局状态（致 3 个"未注册应报错"用例失败）→ 去掉；③ **conftest 的安全包装被我改坏**（目标写成 enhanced 模块并不存在的类 → 抛错被 `except: pass` 静默吞掉 → 包装整体失效、新增 5 条失败）→ 改为两层都包
- **验收三条实测**：① `comm -12`（两文件同名 class）= **0**；② 生产**已无任何**文件从内部层取服务（`create_*` 与 `EnhancedServiceFactory.resolve` 外部调用均为 0）；③ 三层回归 **15 → 15，清单 diff 为空**
- **归因纪律**：`tests/test_enhanced_strategies.py` 有 2 条失败，经**回退对照**确认**原始状态同样失败**（2 failed / 19 passed，`action` 大小写 `'buy'` vs `'BUY'`）→ 属既有问题，非本改动引入
- **范围边界（如实留档）**：卡面「实施方案」③「87 处直连 `adapters.outbound.repositories` 改走端口」**不在验收标准内**，本卡未动——它是**逐点架构改动**（每处要把 `XORMRepository()` 换成经端口的注入，属运行时装配），建议单独开卡分文件推进；87 处的分布与"主仓储都已有端口"这一前提已勘查并留档
- 运行态：应用可导入（100 路由）；本卡 4 次提交：`b3af5a7b`（端口去重）· `45dbf978`（删死件）· `cc92dbe9`（幽灵依赖）· `20c63187`（批次1 迁移 + 入口语义修正）

### 改动文件

- `domain/ports/repository_ports_extended.py`
- `infrastructure/services/service_factory.py`
- `conftest.py`
- `pyproject.toml`
- `application/services/chan_service.py`
- `application/services/daily_orchestrator.py`
- `application/services/data_pipeline_service.py`
- `application/services/strategy_service.py`
- `application/services/stock_pool_service.py`
- `CLAUDE.md`
- `infrastructure/di/container.py`

---
