# ADR-001: 采用六边形架构（端口与适配器模式）

## 状态

**已接受** - 2026-08-15

## 背景

在 quantsys-v2 项目发展过程中，我们遇到了以下架构问题：

1. **层级依赖混乱**：应用层服务直接导入适配器层实现（Repository、DataSource），违反依赖倒置原则
2. **测试困难**：具体实现硬编码在服务中，难以进行单元测试和 mock
3. **可维护性差**：更换数据源或数据库实现需要修改大量应用层代码
4. **代码耦合**：业务逻辑与基础设施代码紧密耦合，难以理解和重构

**问题规模**：
- Phase 1 审计发现 **157 处**应用层违规导入 Repository 实现
- Phase 2 审计发现 **26 处**应用层违规导入 DataSource 实现
- Phase 3 审计发现 **6 处**残留违规

## 决策

我们决定采用**六边形架构（Hexagonal Architecture）**，也称为**端口与适配器模式（Ports and Adapters）**。

### 核心原则

1. **依赖倒置（DIP）**：高层模块（应用层）不依赖低层模块（适配器层），都依赖抽象（端口/接口）
2. **明确边界**：清晰定义领域层、应用层、适配器层的职责和边界
3. **接口抽象**：所有外部依赖（数据库、数据源、外部服务）通过接口访问

### 架构分层

```
┌─────────────────────────────────────────┐
│      Adapters (Inbound - API)          │  ← 入站适配器
│  • Flask Routes                         │
│  • CLI Commands                         │
└─────────────────────────────────────────┘
              ↓ 调用
┌─────────────────────────────────────────┐
│      Application Services               │  ← 应用层
│  • 业务流程编排                         │
│  • 只依赖领域端口（接口）               │
└─────────────────────────────────────────┘
         ↓ 依赖接口
┌─────────────────────────────────────────┐
│      Domain (Ports + Models)            │  ← 领域层（核心）
│  • 端口定义（Ports - 接口）             │
│  • 领域模型（Models）                   │
│  • 领域服务（Business Logic）           │
└─────────────────────────────────────────┘
         ↑ 实现接口
┌─────────────────────────────────────────┐
│      Adapters (Outbound)                │  ← 出站适配器
│  • Repository 实现（ORM）               │
│  • DataSource 实现（API 调用）          │
│  • 外部服务适配器                       │
└─────────────────────────────────────────┘
```

### 实施策略

1. **定义端口层**
   - 创建 `domain/ports/repository_ports_extended.py` - 45 个 Repository 接口
   - 创建 `domain/ports/datasource_ports.py` - DataSource 接口

2. **应用层重构**
   - 应用层只导入 `domain.ports.*` 和 `domain.models.*`
   - 使用局部导入（在 `__init__` 中）获取具体实现
   - 所有依赖使用接口类型注解

3. **适配器层实现**
   - Repository 实现类继承接口：`class XxxORMRepository(IXxxRepository)`
   - DataSource 实现类继承接口：`class XxxProvider(IXxxProvider)`

4. **代码示例**

   **Before (❌ 违规)**:
   ```python
   from adapters.outbound.repositories.stock_repository import StockORMRepository
   
   class StockService:
       def __init__(self):
           self.repo = StockORMRepository()
   ```

   **After (✅ 符合规范)**:
   ```python
   from domain.ports.repository_ports_extended import IStockRepository
   
   class StockService:
       def __init__(self):
           from adapters.outbound.repositories.stock_repository import StockORMRepository
           self.repo: IStockRepository = StockORMRepository()
   ```

## 结果

### 三阶段重构成果

| 阶段 | 目标 | 起始违规 | 完成违规 | 改进 |
|------|------|---------|---------|------|
| Phase 1 | Repository 接口迁移 | 157 | 26 | -83% |
| Phase 2 | DataSource 接口迁移 | 26 | 6 | -77% |
| Phase 3 | 残留违规手工整改 | 6 | 0 | -100% |
| **总计** | - | **157** | **0** | **-100%** |

### 效益

1. **架构清晰**
   - 层级职责明确，依赖方向正确
   - 应用层完全不依赖适配器层实现

2. **可测试性提升**
   - 接口可以轻松 mock，单元测试更容易编写
   - 测试不需要真实数据库或外部服务

3. **可维护性增强**
   - 更换数据源只需修改适配器层，应用层不受影响
   - 新增数据源只需实现接口，无需修改现有代码

4. **团队协作改善**
   - 明确的代码规范和检查工具
   - pre-commit hook 和 CI 自动检查违规

### 遗留问题

- **7 处新违规**：来自 main 分支的 ML 相关代码（ml_train_task.py, manipulation_detector.py 等），导入 `adapters.shared.ml_helpers`
- **处理方案**：待评估是否将 `adapters.shared` 抽象为接口或移至 `infrastructure` 层

## 配套措施

### 1. 文档

- **[CODING_STANDARDS.md](../CODING_STANDARDS.md)** - 完整编码规范（18 节，6000+ 字）
- **[ARCHITECTURE_QUICK_REFERENCE.md](docs/ARCHITECTURE_QUICK_REFERENCE.md)** - 快速参考卡片
- **[DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md)** - 新人入门指南

### 2. 自动化工具

- **检测工具**：`tools/analyze_layer_violations.py` - 分析架构违规
- **Pre-commit Hook**：`.git-hooks/pre-commit` - 提交前自动检查
- **CI 集成**：`.github/workflows/architecture-check.yml` - PR 自动检查

### 3. 团队培训

- Code Review 检查点清单
- 常见违规及修复示例
- 接口位置速查表

## 经验教训

### 成功经验

1. **渐进式重构**：分三个阶段逐步推进，每个阶段都有明确目标和验证
2. **自动化优先**：编写自动化工具（迁移脚本、检测工具），而非手工修改
3. **文档先行**：在要求团队遵守规范前，先提供完整文档和示例

### 遇到的挑战

1. **局部导入的权衡**：使用局部导入避免顶层违规，但牺牲了一些可读性
2. **接口爆炸**：45 个 Repository 接口的维护成本
3. **历史债务**：持续有新代码违反规范，需要 CI 强制执行

### 未来改进方向

1. **依赖注入框架**：考虑引入轻量级 DI 框架（如 `dependency-injector`），避免手动局部导入
2. **接口自动生成**：从实现类自动生成接口定义，减少维护成本
3. **架构测试**：编写架构测试（ArchUnit 风格），在测试阶段就发现违规

## 参考资料

### 内部文档

- [Phase 1 完成报告](docs/superpowers/specs/2026-08-15-phase1-repository-migration-report.md)
- [Phase 2 完成报告](docs/superpowers/specs/2026-08-15-phase2-datasource-migration-report.md)
- [Phase 3 完成报告](docs/superpowers/specs/2026-08-15-phase3-remaining-violations-report.md)
- [架构审计进度](docs/architecture-audit-progress.md)

### 外部资料

- [Hexagonal Architecture - Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture/)
- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)

## 决策者

- **提出者**：Architecture Team
- **批准者**：Tech Lead
- **实施者**：Architecture Team + AI Assistant (Claude)

## 时间线

- **2026-08-15**：Phase 1 完成（Repository 迁移）
- **2026-08-15**：Phase 2 完成（DataSource 迁移）
- **2026-08-15**：Phase 3 完成（残留违规清理）
- **2026-08-15**：编码规范文档发布
- **2026-08-15**：ADR 记录归档

---

**状态**: ✅ 已实施并验证  
**下一步审查**: 2026-09-15（一个月后评估效果）
