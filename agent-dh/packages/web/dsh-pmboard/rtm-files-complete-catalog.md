═══════════════════════════════════════════════════════════════════════════════
  RTM 文件生成完整清单
═══════════════════════════════════════════════════════════════════════════════

## RTM 文件体系（5 类 + 任务详情）

根据 filesForTrigger() 函数（packages/tools/reqboard/src/rtm/generator.ts），
每个触发点会生成/更新以下 RTM YAML 文件：

### 1. rtm-lifecycle.yml - 生命周期主文件
**生成时机**：所有触发点都会更新此文件
**内容**：需求的完整生命周期快照
- 需求基本信息（ID、标题、分类、状态）
- 绑定窗口（sourceSessionId）
- 启用的阶段（enabled stages）
- 当前阶段与推进历史
- 最后更新时间

**触发点**：
- create ✅
- submit:requirement ✅
- confirm:artifact ✅
- submit:design ✅
- confirm:plan ✅
- bind ✅
- submit:verification ✅

### 2. rtm-brainstorming.yml - 需求分析阶段
**生成时机**：提交或确认需求文档时
**内容**：
- FR（功能需求）列表与编号
- AC（验收标准）列表
- 需求覆盖度统计
- 需求文档元数据

**触发点**：
- submit:requirement ✅
- confirm:artifact ✅

### 3. rtm-design.yml - 设计阶段 ⭐ 关键文件
**生成时机**：提交或确认设计文档时
**内容**：
- **fr_to_design 映射**（FR → 设计章节的 serves 标注）
- **设计覆盖度统计**（covered/total/percentage）
- 设计文档清单
- 未覆盖的 FR 列表

**触发点**：
- confirm:artifact ✅
- submit:design ✅（**门禁预检点**：覆盖度必须 100%）

**门禁**：设计覆盖度门禁（最严格）
- 要求：所有 FR 必须有 serves: FR-x 标注
- 覆盖度：100%
- 未过：当场拒绝提交且不登记

### 4. rtm-decomposing.yml - 拆分阶段
**生成时机**：批准计划或任务状态变更时
**内容**：
- **implementation_coverage**（实施覆盖度）
  - FR → 设计 → 任务的追溯链
  - 设计章节被任务接收情况
- 拆分计划元数据
- 任务 DAG 结构

**触发点**：
- confirm:plan ✅
- task:status ✅（任务状态变化后刷新覆盖度）
- task:report ✅（任务汇报后刷新覆盖度）

**门禁**：编号链完整性门禁
- 要求：FR → 设计 → 任务追溯链完整
- 未过：落章但不推进，返回 gate_failure

### 5. rtm-implementing.yml - 实施阶段
**生成时机**：批准计划或任务变更时
**内容**：
- 任务列表与状态
- 任务依赖关系（DAG）
- 任务完成度统计
- 工作流阶段分布

**触发点**：
- confirm:plan ✅
- task:status ✅
- task:report ✅

### 6. rtm-implementing/<task>.yml - 任务详情文件
**生成时机**：任务状态变更或任务汇报时
**内容**：
- 单个任务的详细信息
- 任务汇报历史
- 工作流阶段推断
- 验收状态

**触发点**：
- task:status ✅
- task:report ✅

**文件命名**：rtm-implementing/<task-id>.yml
**示例**：rtm-implementing/t-20240927-123456.yml

### 7. rtm-accepting.yml - 验收阶段
**生成时机**：提交验收材料时
**内容**：
- **acceptance_tracking**（验收追踪）
- **testing_coverage**（测试覆盖度）
- 验收单项目清单
- E2E 测试覆盖情况
- 验收材料元数据

**触发点**：
- submit:verification ✅

**门禁**：文档完整性门禁
- 要求：9 类文档完整性检查
- 未过：门禁预检标记但不阻断

═══════════════════════════════════════════════════════════════════════════════

## 触发点 → 文件映射表

| 触发点 | 生成/更新的文件 | 主要内容 | 门禁检查 |
|--------|----------------|---------|---------|
| **create** | rtm-lifecycle.yml | 生命周期骨架 | 无 |
| **submit:requirement** | rtm-brainstorming.yml<br>rtm-lifecycle.yml | 需求覆盖度<br>生命周期更新 | 无 |
| **confirm:artifact** | rtm-brainstorming.yml<br>rtm-design.yml<br>rtm-lifecycle.yml | 需求确认<br>设计覆盖度<br>生命周期更新 | 无 |
| **submit:design** | rtm-design.yml<br>rtm-lifecycle.yml | **设计覆盖度**<br>生命周期更新 | ✅ 100% 覆盖度 |
| **confirm:plan** | rtm-decomposing.yml<br>rtm-implementing.yml<br>rtm-lifecycle.yml | **实施覆盖度**<br>任务骨架<br>生命周期更新 | ✅ 编号链完整性 |
| **task:status** | rtm-decomposing.yml<br>rtm-implementing.yml<br>rtm-implementing/&lt;task&gt;.yml | 实施覆盖度刷新<br>任务状态更新<br>任务详情 | 无 |
| **task:report** | rtm-decomposing.yml<br>rtm-implementing.yml<br>rtm-implementing/&lt;task&gt;.yml | 实施覆盖度刷新<br>任务汇报<br>任务详情 | 无 |
| **bind** | rtm-lifecycle.yml | 窗口绑定更新 | 无 |
| **submit:verification** | rtm-accepting.yml<br>rtm-lifecycle.yml | **验收追踪**<br>生命周期更新 | ✅ 文档完整性 |

═══════════════════════════════════════════════════════════════════════════════

## RTM 文件存放位置

所有 RTM 文件存放在需求目录下：

```
docs/requirements/REQ-xxxxxx/
├── requirement.md              # 需求文档
├── design/                     # 设计文档目录
│   ├── architecture.md
│   ├── interface.md
│   └── data-model.md
├── decomposition.md            # 拆分计划
├── tasks/                      # 任务卡目录
│   ├── t-xxx.md
│   └── t-yyy.md
└── rtm/                        # RTM 文件目录 ⭐
    ├── rtm-lifecycle.yml       # 生命周期主文件（所有触发点都更新）
    ├── rtm-brainstorming.yml   # 需求分析阶段
    ├── rtm-design.yml          # 设计阶段（含 fr_to_design 映射）
    ├── rtm-decomposing.yml     # 拆分阶段（含 implementation_coverage）
    ├── rtm-implementing.yml    # 实施阶段
    ├── rtm-accepting.yml       # 验收阶段（含 acceptance_tracking）
    └── rtm-implementing/       # 任务详情目录
        ├── t-xxx.yml
        └── t-yyy.yml
```

═══════════════════════════════════════════════════════════════════════════════

## 关键覆盖度数据（供门禁使用）

### 1. 设计覆盖度（design_coverage）
**来源**：rtm-design.yml  
**计算**：covered_frs / total_frs * 100%  
**门禁**：submit:design 时检查，必须 100%  
**数据结构**：
```yaml
coverage:
  design:
    total: 10           # 总 FR 数
    covered: 10         # 有 serves 标注的 FR 数
    percentage: 100     # 覆盖率
    uncovered: []       # 未覆盖的 FR 列表
```

### 2. 实施覆盖度（implementation_coverage）
**来源**：rtm-decomposing.yml  
**计算**：已被任务接收的设计章节数 / 总设计章节数  
**门禁**：confirm:plan 时检查编号链完整性  
**数据结构**：
```yaml
coverage:
  implementation:
    total: 15           # 总设计章节数
    covered: 15         # 被任务接收的章节数
    percentage: 100     # 覆盖率
    unreceived: []      # 未被任务接收的章节列表
```

### 3. 测试覆盖度（testing_coverage）
**来源**：rtm-accepting.yml  
**计算**：有 E2E 测试的任务数 / 总任务数  
**门禁**：submit:verification 时预检（不阻断）  
**数据结构**：
```yaml
coverage:
  testing:
    total: 20           # 总任务数
    tested: 18          # 有测试的任务数
    percentage: 90      # 测试覆盖率
    untested: [...]     # 无测试的任务列表
```

═══════════════════════════════════════════════════════════════════════════════

## 总结

✅ **RTM 文件体系完整**

- **7 类文件**：1 个主文件（lifecycle）+ 5 个阶段文件 + 任务详情
- **9 个触发点**：覆盖需求全生命周期
- **3 道门禁**：设计覆盖度、编号链、文档完整性
- **失败不打断**：所有异常都被吞掉并结构化返回（FR-9）

### 最关键的三个文件

1. **rtm-design.yml** - 设计覆盖度门禁数据源
2. **rtm-decomposing.yml** - 实施覆盖度门禁数据源
3. **rtm-accepting.yml** - 验收追踪数据源

这些文件支撑了 PMBoard 的三级追溯链：
- Level 1: 需求 ← 设计（rtm-design.yml）
- Level 2: 设计 ← 任务（rtm-decomposing.yml）
- Level 3: 任务 ← 测试（rtm-accepting.yml）

═══════════════════════════════════════════════════════════════════════════════