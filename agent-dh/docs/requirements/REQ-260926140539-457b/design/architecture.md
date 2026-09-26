---
requirement_id: REQ-260926140539-457b
design_type: architecture
version: 1.0
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
---

# RTM 系统架构设计

## 目标 serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11

在 dsh-pmboard 中实现 RTM YAML 追溯基础设施，通过预构建索引和文件分离策略，将 Dive 模式决策延迟从 500ms 降至 2ms（250x 提升），并为会话节点提供完整的四级追溯链可视化（需求 → 设计 → 任务 → 测试）。

---

## 系统架构 serves: FR-1, FR-2, FR-7
### 整体架构 serves: FR-1, FR-2, FR-7

```
┌─────────────────────────────────────────────────────────────────────┐
│  Dive 模式（AI Agent）                                               │
│  • 读取 RTM (~2ms) 快速决策                                          │
│  • 基于覆盖度统计判断推进                                             │
│  • 节点输入包注入 RTM 数据                                           │
└─────────────────────────────────────────────────────────────────────┘
       ↓ 读取                          ↑ 展示
┌─────────────────────────────────────────────────────────────────────┐
│  RTM 文件系统（YAML）                                                │
│  • rtm-lifecycle.yml（全局状态，~50行）                              │
│  • rtm-brainstorming.yml（需求分析，~40行）                          │
│  • rtm-design.yml（设计，~60行）                                     │
│  • rtm-decomposing.yml（拆分，~80行）                                │
│  • rtm-implementing.yml（实施汇总，~50行）                           │
│  • rtm-implementing/*.yml（任务详情，按需读取）                       │
│  • rtm-accepting.yml（验收，~60行）                                  │
└─────────────────────────────────────────────────────────────────────┘
       ↑ 生成/更新（7个触发点）         ↓ 数据源
┌─────────────────────────────────────────────────────────────────────┐
│  RTM 生成引擎（TypeScript）                                          │
│  • RTMGenerator 类（核心生成器）                                     │
│  • RTMParser 类（文档解析）                                          │
│  • RTMValidator 类（覆盖度门禁）                                     │
│  • 7 个触发点集成（reqboard 工具钩子）                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 核心模块设计 serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
### 1. RTM 生成引擎 serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
serves: FR-1, FR-2, FR-6

**位置**：agent-dh/packages/pmboard/src/rtm/

**类结构**：

TypeScript 接口定义见 rtm-schema.md 文档。

核心方法：
- generateLifecycle() - 生成全局生命周期
- generateBrainstorming() - 生成需求分析节点
- generateDesign() - 生成设计节点
- generateDecomposing() - 生成拆分节点
- generateImplementing() - 生成实施节点
- updateTaskStatus() - 更新任务状态
- generateAccepting() - 生成验收节点

### 2. 文档解析器 serves: FR-3, FR-4

**位置**：agent-dh/packages/pmboard/src/rtm/parser.ts

核心方法：
- parseRequirementFRs() - 提取 FR 列表
- parseDesignSections() - 提取设计章节
- parseTaskImplements() - 提取任务实现关系
- parseTestCovers() - 提取测试覆盖关系

### 3. 覆盖度验证器 serves: FR-5, FR-10

**位置**：agent-dh/packages/pmboard/src/rtm/validator.ts

门禁规则：
- design: 要求 100%
- decomposing: 要求 100%
- accepting: 要求 ≥80%

---

## 验收口径 serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
### 1. 端到端测试 serves: FR-1~FR-11
serves: FR-1, FR-2, FR-3, FR-4, FR-5

```bash
cd agent-dh
npm test -- rtm-e2e.test.ts
```

预期结果：
- ✓ 立项后生成 rtm-lifecycle.yml
- ✓ 提交需求后生成 rtm-brainstorming.yml（提取 FR）
- ✓ 提交设计后生成 rtm-design.yml（覆盖度门禁）
- ✓ 批准计划后生成 rtm-decomposing.yml
- ✓ 任务变更后更新 rtm-implementing/*.yml
- ✓ 提交验收后生成 rtm-accepting.yml

### 2. 性能测试 serves: FR-8, FR-10

```bash
npm test -- rtm-performance.test.ts
```

预期结果：
- ✓ Dive 决策 < 5ms（vs 原来 500ms）
- ✓ 任务更新 < 10ms
- ✓ 性能提升 250x

### 3. 覆盖度门禁测试 serves: FR-5

```bash
npm test -- rtm-gate.test.ts
```

预期结果：
- ✓ 设计覆盖度 < 100% 时拒绝
- ✓ 实施覆盖度 < 100% 时拒绝
- ✓ 测试覆盖度 < 80% 时拒绝

### 4. StageOverview 集成测试 serves: FR-7

```bash
curl http://localhost:13080/api/stage-overview/REQ-260926140539-457b
```

预期返回包含 traceability 和 coverage 数据。

### 5. 异常测试 serves: FR-9

```bash
npm test -- rtm-fallback.test.ts
```

预期结果：
- ✓ RTM 缺失时自动重新生成
- ✓ 格式错误时不崩溃
- ✓ 并发更新无冲突