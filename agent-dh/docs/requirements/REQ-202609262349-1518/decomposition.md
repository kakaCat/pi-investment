# REQ-202609262349-1518 拆分计划

## §1 根编号 ↔ 任务卡 对照表（RTM 追溯用）

> 本表供 RTM 生成器解析（`parseDecompositionServes`）：**FR 单元格紧跟台账任务 id 单元格**即建立
> 「该任务服务该 FR」的映射；设计章节的 serves 含同一 FR 时，design → task 追溯即成立。
> 任务 id 为 `reqboard_decompose` 落库后的真实台账 id（非计划 key）。

| 根编号 | 任务卡 id | 任务 |
|--------|-----------|------|
| FR-1 | t-9d53f4 | 扩展台账数据模型 |
| FR-1 | t-8a2918 | decomposing 阶段 RTM 生成 |
| FR-1 | t-052ac0 | implementing 阶段 RTM 生成 |
| FR-1 | t-7d6e13 | accepting 阶段 RTM 生成 |
| FR-1 | t-dbad8b | 文档更新 |
| FR-2 | t-9d53f4 | 扩展台账数据模型 |
| FR-2 | t-3067d0 | 台账数据迁移 |
| FR-3 | t-8a2918 | decomposing 阶段 RTM 生成 |
| FR-3 | t-052ac0 | implementing 阶段 RTM 生成 |
| FR-3 | t-7d6e13 | accepting 阶段 RTM 生成 |
| FR-3 | t-8eee40 | 端到端测试 |
| FR-4 | t-799c20 | 文档标注解析器 |
| FR-5 | t-51e360 | 追溯关系构建器 |
| FR-5 | t-8eee40 | 端到端测试 |
| FR-6 | t-09dcfc | 覆盖度计算器 |
| FR-6 | t-67e3e4 | StatusTool 集成覆盖度 |
| FR-6 | t-8eee40 | 端到端测试 |
| FR-7 | t-0de514 | 覆盖度门禁 |
| FR-7 | t-8eee40 | 端到端测试 |
| FR-8 | t-bbf915 | RTM 快速读取接口 |
| FR-8 | t-67e3e4 | StatusTool 集成覆盖度 |
| FR-8 | t-91f04c | 性能测试 |
| FR-8 | t-dbad8b | 文档更新 |
| FR-9 | t-3067d0 | 台账数据迁移 |

## 改动盘点

### 一、现状分析

**已实现部分**：
1. ✅ RTM YAML 基础结构（rtm-lifecycle.yml, rtm-brainstorming.yml, rtm-design.yml）
2. ✅ 设计阶段的 FR → 设计章节追溯（rtm-design.yml 中的 `serves` 字段）
3. ✅ 部分触发点接线（create, submit:requirement, confirm:artifact, submit:design）
4. ✅ RTM 健康检查机制（rtm-health.ts）

**待实现部分**：
1. ❌ 台账数据模型扩展（schemaVersion 8 → 9，新增 artifacts/designServes/implements 字段）
2. ❌ 完整的 7 个触发点 RTM 生成（decomposing/implementing/accepting 阶段）
3. ❌ 文档标注解析器（解析 `<!-- serves: FR-X -->` 等标注）
4. ❌ 追溯关系索引引擎（design_to_tasks, task_to_tests）
5. ❌ 覆盖度统计与门禁（设计 100%、实施 100%、测试 ≥80%）
6. ❌ RTM 快速读取接口（readRTM 函数）
7. ❌ 数据迁移脚本（schemaVersion 9 迁移）

### 二、改动文件清单

#### 新增文件（6个）

1. **`src/domain/rtm/types.ts`** - RTM 核心类型定义
2. **`src/domain/rtm/parser.ts`** - 文档标注解析器
3. **`src/domain/rtm/traceability.ts`** - 追溯关系构建器
4. **`src/domain/rtm/coverage.ts`** - 覆盖度计算器
5. **`src/domain/rtm/reader.ts`** - RTM 读取接口
6. **`scripts/migrate-reqboard-schema-v9.ts`** - 数据迁移脚本

#### 修改文件（8个）

1. **`src/shared/protocol.ts`** - 扩展 Requirement/Task 类型定义
2. **`src/application/internal/rtm-yaml.ts`** - 补全 decomposing/implementing/accepting 触发点
3. **`src/application/use-cases/SubmitArtifact.ts`** - 集成覆盖度门禁
4. **`src/application/use-cases/Decompose.ts`** - 生成 rtm-decomposing.yml
5. **`src/application/use-cases/ReportTask.ts`** - 更新 rtm-implementing/*.yml
6. **`src/application/use-cases/SubmitVerification.ts`** - 生成 rtm-accepting.yml
7. **`src/adapters/JsonLedgerRepository.ts`** - 支持新字段读写
8. **`src/tools/StatusTool/StatusTool.ts`** - 返回覆盖度统计

---

## 任务表

### 第一批：数据模型与基础设施（并行）

**t1-schema-types** - 扩展台账数据模型  
phase: doc | side: backend | depends_on: []

**实施方案**：
1. 修改 `src/shared/protocol.ts`，扩展类型定义：
   - `RequirementRecord.artifacts?: Artifact[]`（kind/path/stage/confirmed/confirmedAt/registeredAt）
   - `TaskRecord.designServes?: string[]`（服务的 FR 列表，如 ["FR-1", "FR-2"]）
   - `TaskRecord.implements?: string`（实现的设计章节，如 "design/arch#1.1"）
2. 添加 `Artifact` 接口定义（kind: "requirement"|"design"|"plan"|"verification"|"archive"）
3. 创建 `src/domain/rtm/types.ts`，定义 RTM 文件结构：
   - `RTMFile` 基础接口（metadata/inputs/outputs/traceability/coverage）
   - `RTMLifecycle` / `RTMBrainstorming` / `RTMDesign` 等各节点类型
   - `TraceabilityMap`（fr_to_design / design_to_tasks / task_to_tests）
   - `CoverageStats`（total/covered/rate/uncovered）

**验收标准**：
```bash
# 1. TypeScript 编译通过
cd packages/web/dsh-pmboard && pnpm build

# 2. 类型定义完整
grep "artifacts?: Artifact\[\]" src/shared/protocol.ts
grep "designServes?: string\[\]" src/shared/protocol.ts
grep "implements?: string" src/shared/protocol.ts

# 3. RTM 类型导出成功
grep "export interface RTMFile" src/domain/rtm/types.ts
grep "export interface TraceabilityMap" src/domain/rtm/types.ts
```

---

**t2-ledger-migration** - 台账数据迁移  
phase: implement | side: backend | depends_on: [t1-schema-types]

**实施方案**：
1. 创建 `scripts/migrate-reqboard-schema-v9.ts`：
   - 读取 `.dsh-data/dsh-reqboard.json`
   - 备份到 `dsh-reqboard.json.bak-v8`
   - 遍历所有需求，添加 `artifacts: []`（如果缺失）
   - 遍历所有任务，添加 `designServes: null`, `implements: null`（如果缺失）
   - 更新 `schemaVersion: 9`
   - 写回 `.dsh-data/dsh-reqboard.json`
2. 修改 `src/adapters/JsonLedgerRepository.ts`：
   - `loadLedger()` 读取时兼容旧字段（缺失字段视为默认值）
   - `saveLedger()` 写入时包含新字段
   - 增加 schemaVersion 验证（>= 9）

**验收标准**：
```bash
# 1. 迁移脚本可执行
node scripts/migrate-reqboard-schema-v9.ts

# 2. 备份文件生成
test -f .dsh-data/dsh-reqboard.json.bak-v8 && echo "PASS" || echo "FAIL"

# 3. schemaVersion 已更新
jq '.schemaVersion' .dsh-data/dsh-reqboard.json  # 期望: 9

# 4. 新字段存在
jq '.requirements[0].artifacts' .dsh-data/dsh-reqboard.json  # 期望: []
jq '.tasks[0].designServes' .dsh-data/dsh-reqboard.json      # 期望: null

# 5. 增量迁移幂等（再次运行不报错）
node scripts/migrate-reqboard-schema-v9.ts
```

---

**t3-doc-parser** - 文档标注解析器  
phase: implement | side: backend | depends_on: [t1-schema-types]

**实施方案**：
1. 创建 `src/domain/rtm/parser.ts`，实现 `DocumentParser` 类：
   - `parseServes(content: string): string[]` - 解析 `<!-- serves: FR-1, FR-2 -->`
   - `parseImplements(content: string): string | null` - 解析 `<!-- implements: design/arch#1.1 -->`
   - `parseCovers(content: string): string[]` - 解析 `<!-- covers: t-354ea0 -->`
   - `extractFRs(content: string): string[]` - 提取文档中的所有 FR-N 编号
2. 支持逗号分隔的多值（`FR-1, FR-2`）
3. 去除空白符和注释符（`<!-- -->`）
4. 返回规范化的 ID 数组（如 `["FR-1", "FR-2"]`）

**验收标准**：
```bash
# 1. 单元测试通过
cd packages/web/dsh-pmboard && pnpm test src/domain/rtm/parser.test.ts

# 2. 解析 serves 标注
echo '<!-- serves: FR-1, FR-2 -->' | node -e "
  const { DocumentParser } = require('./dist/domain/rtm/parser.js');
  const p = new DocumentParser();
  console.log(p.parseServes(require('fs').readFileSync(0, 'utf-8')));
"  # 期望: ["FR-1", "FR-2"]

# 3. 解析 implements 标注
echo '<!-- implements: design/arch#1.1 -->' | node -e "
  const { DocumentParser } = require('./dist/domain/rtm/parser.js');
  const p = new DocumentParser();
  console.log(p.parseImplements(require('fs').readFileSync(0, 'utf-8')));
"  # 期望: "design/arch#1.1"
```

---

### 第二批：追溯与覆盖度（依赖第一批）

**t4-traceability** - 追溯关系构建器  
phase: implement | side: backend | depends_on: [t3-doc-parser]

**实施方案**：
1. 创建 `src/domain/rtm/traceability.ts`，实现 `TraceabilityBuilder` 类：
   - `buildFRToDesign(designDocs: DesignDoc[]): Map<string, string[]>` - 构建 FR → 设计章节映射
   - `buildDesignToTasks(tasks: Task[]): Map<string, string[]>` - 构建设计章节 → 任务映射
   - `buildTaskToTests(testCases: TestCase[]): Map<string, string[]>` - 构建任务 → 测试用例映射
2. 集成 `DocumentParser` 解析标注
3. 返回三级追溯链：`{ fr_to_design, design_to_tasks, task_to_tests }`

**验收标准**：
```bash
# 1. 单元测试通过
pnpm test src/domain/rtm/traceability.test.ts

# 2. FR → 设计映射正确
node -e "
  const { TraceabilityBuilder } = require('./dist/domain/rtm/traceability.js');
  const docs = [{ file: 'design/arch.md', content: '<!-- serves: FR-1 -->' }];
  const tb = new TraceabilityBuilder();
  const map = tb.buildFRToDesign(docs);
  console.log(map.get('FR-1'));
"  # 期望: ["design/arch.md"]

# 3. 设计 → 任务映射正确
node -e "
  const { TraceabilityBuilder } = require('./dist/domain/rtm/traceability.js');
  const tasks = [{ id: 't-354ea0', implements: 'design/arch#1.1' }];
  const tb = new TraceabilityBuilder();
  const map = tb.buildDesignToTasks(tasks);
  console.log(map.get('design/arch#1.1'));
"  # 期望: ["t-354ea0"]
```

---

**t5-coverage-calculator** - 覆盖度计算器  
phase: implement | side: backend | depends_on: [t4-traceability]

**实施方案**：
1. 创建 `src/domain/rtm/coverage.ts`，实现 `CoverageCalculator` 类：
   - `calculateDesignCoverage(frs: string[], traceability: TraceabilityMap): CoverageStats`
     - total = FR 总数
     - covered = 有设计章节服务的 FR 数
     - rate = covered / total
     - uncovered = 缺少设计的 FR 列表
   - `calculateImplementationCoverage(designs: string[], traceability: TraceabilityMap): CoverageStats`
     - total = 设计章节总数
     - covered = 有任务实现的设计章节数
   - `calculateTestCoverage(tasks: string[], traceability: TraceabilityMap): CoverageStats`
     - total = 任务总数
     - covered = 有测试用例覆盖的任务数
2. 返回统计对象：`{ total, covered, rate, uncovered }`

**验收标准**：
```bash
# 1. 单元测试通过
pnpm test src/domain/rtm/coverage.test.ts

# 2. 设计覆盖度计算正确
node -e "
  const { CoverageCalculator } = require('./dist/domain/rtm/coverage.js');
  const frs = ['FR-1', 'FR-2', 'FR-3'];
  const traceability = { fr_to_design: new Map([['FR-1', ['design/a.md']], ['FR-2', ['design/b.md']]]) };
  const calc = new CoverageCalculator();
  const stats = calc.calculateDesignCoverage(frs, traceability);
  console.log(stats);
"  # 期望: { total: 3, covered: 2, rate: 0.67, uncovered: ['FR-3'] }

# 3. 覆盖度 100% 时 uncovered 为空
node -e "
  const { CoverageCalculator } = require('./dist/domain/rtm/coverage.js');
  const frs = ['FR-1'];
  const traceability = { fr_to_design: new Map([['FR-1', ['design/a.md']]]) };
  const calc = new CoverageCalculator();
  const stats = calc.calculateDesignCoverage(frs, traceability);
  console.log(stats.uncovered.length === 0 ? 'PASS' : 'FAIL');
"  # 期望: PASS
```

---

**t6-coverage-gate** - 覆盖度门禁  
phase: implement | side: backend | depends_on: [t5-coverage-calculator]

**实施方案**：
1. 在 `src/application/internal/rtm-yaml.ts` 中实现 `checkCoverageGate()` 函数：
   - 设计门禁：`submit(kind=design)` 时检查设计覆盖度 >= 100%
   - 实施门禁：`submit(kind=plan)` 时检查实施覆盖度 >= 100%
   - 测试门禁：`submit(kind=verification)` 时检查测试覆盖度 >= 80%
2. 不足时抛错 `COVERAGE_INSUFFICIENT`，包含：
   - `kind`: "design" | "implementation" | "testing"
   - `rate`: 当前覆盖度（如 0.67）
   - `threshold`: 要求阈值（1.0 或 0.8）
   - `uncovered`: 缺口清单（FR / 设计章节 / 任务的 ID 数组）
3. 修改 `src/application/use-cases/SubmitArtifact.ts`，集成门禁检查

**验收标准**：
```bash
# 1. 设计门禁拦截不足的提交（创建测试需求，故意缺少 FR-3 的设计）
curl -X POST http://localhost:13080/api/pmboard/submit \
  -d '{"requirementId":"REQ-test","kind":"design"}' \
  -H "Content-Type: application/json"
# 期望: {"error":"COVERAGE_INSUFFICIENT","kind":"design","rate":0.67,"uncovered":["FR-3"]}

# 2. 设计门禁通过完整的提交（补充 FR-3 的设计后再提交）
curl -X POST http://localhost:13080/api/pmboard/submit \
  -d '{"requirementId":"REQ-test","kind":"design"}' \
  -H "Content-Type: application/json"
# 期望: {"success":true}

# 3. 测试门禁接受 80% 覆盖度
curl -X POST http://localhost:13080/api/pmboard/submit \
  -d '{"requirementId":"REQ-test","kind":"verification"}' \
  -H "Content-Type: application/json"
# 覆盖度 0.8 时通过
```

---

### 第三批：RTM 生成与读取（依赖第二批）

**t7-rtm-decomposing** - decomposing 阶段 RTM 生成  
phase: implement | side: backend | depends_on: [t4-traceability, t5-coverage-calculator]

**实施方案**：
1. 修改 `src/application/internal/rtm-yaml.ts`，补全 `confirm:plan` 触发点：
   - 读取批准的拆分计划（decomposition.md）
   - 解析任务表中的 `implements` 标注
   - 调用 `TraceabilityBuilder.buildDesignToTasks()`
   - 调用 `CoverageCalculator.calculateImplementationCoverage()`
   - 生成 `rtm-decomposing.yml`（包含 design_to_tasks 映射和实施覆盖度）
2. 修改 `src/application/use-cases/Decompose.ts`，调用 RTM 生成
3. 生成文件结构：
   ```yaml
   metadata: { stage: decomposing, version, generated_at }
   inputs: { design_sections: [...] }
   outputs: { tasks: [...] }
   traceability: { design_to_tasks: {...} }
   coverage: { implementation: { total, covered, rate, uncovered } }
   ```

**验收标准**：
```bash
# 1. 批准拆分计划后生成 RTM
reqboard_submit(kind=plan, requirementId="REQ-test")
reqboard_ask_confirm(target=plan, requirementId="REQ-test")

# 2. rtm-decomposing.yml 文件生成
test -f docs/requirements/REQ-test/rtm-decomposing.yml && echo "PASS" || echo "FAIL"

# 3. design_to_tasks 映射完整
grep "design_to_tasks:" docs/requirements/REQ-test/rtm-decomposing.yml

# 4. 实施覆盖度存在
grep "implementation:" docs/requirements/REQ-test/rtm-decomposing.yml
grep "rate:" docs/requirements/REQ-test/rtm-decomposing.yml
```

---

**t8-rtm-implementing** - implementing 阶段 RTM 生成  
phase: implement | side: backend | depends_on: [t7-rtm-decomposing]

**实施方案**：
1. 修改 `src/application/internal/rtm-yaml.ts`，补全 `task:status` / `task:report` 触发点：
   - 任务状态变更时更新 `rtm-implementing.yml`（任务进度统计）
   - 任务汇报时生成 `rtm-implementing/{task_id}.yml`（单任务详情）
2. 修改 `src/application/use-cases/ReportTask.ts`，调用 RTM 生成
3. 生成文件结构：
   ```yaml
   # rtm-implementing.yml（总览）
   metadata: { stage: implementing, version }
   outputs: { tasks: [...], progress: { total, completed, in_progress } }
   
   # rtm-implementing/t-{task_id}.yml（单任务）
   metadata: { task_id, version }
   task: { id, title, status, phase, side }
   implements: "design/arch#1.1"
   reports: [{ at, summary, phase }]
   ```

**验收标准**：
```bash
# 1. 任务状态变更后更新 RTM
reqboard_task_move(taskId="t-354ea0", action="start")
grep "in_progress:" docs/requirements/REQ-test/rtm-implementing.yml

# 2. 任务汇报后生成详情文件
reqboard_task_report(taskId="t-354ea0", summary="完成接口实现")
test -f docs/requirements/REQ-test/rtm-implementing/t-354ea0.yml && echo "PASS" || echo "FAIL"

# 3. implements 字段存在
grep "implements:" docs/requirements/REQ-test/rtm-implementing/t-354ea0.yml

# 4. 汇报记录存在
grep "reports:" docs/requirements/REQ-test/rtm-implementing/t-354ea0.yml
```

---

**t9-rtm-accepting** - accepting 阶段 RTM 生成  
phase: implement | side: backend | depends_on: [t8-rtm-implementing, t3-doc-parser]

**实施方案**：
1. 修改 `src/application/internal/rtm-yaml.ts`，补全 `submit:verification` 触发点：
   - 读取测试用例文档（test-cases.md 或验收单）
   - 解析 `covers` 标注
   - 调用 `TraceabilityBuilder.buildTaskToTests()`
   - 调用 `CoverageCalculator.calculateTestCoverage()`
   - 生成 `rtm-accepting.yml`（包含 task_to_tests 映射和测试覆盖度）
2. 修改 `src/application/use-cases/SubmitVerification.ts`，调用 RTM 生成
3. 生成文件结构：
   ```yaml
   metadata: { stage: accepting, version }
   inputs: { tasks: [...] }
   outputs: { test_cases: [...] }
   traceability: { task_to_tests: {...} }
   coverage: { testing: { total, covered, rate, uncovered } }
   ```

**验收标准**：
```bash
# 1. 提交验收材料后生成 RTM
reqboard_submit(kind=verification, requirementId="REQ-test")

# 2. rtm-accepting.yml 文件生成
test -f docs/requirements/REQ-test/rtm-accepting.yml && echo "PASS" || echo "FAIL"

# 3. task_to_tests 映射完整
grep "task_to_tests:" docs/requirements/REQ-test/rtm-accepting.yml

# 4. 测试覆盖度存在
grep "testing:" docs/requirements/REQ-test/rtm-accepting.yml
grep "rate:" docs/requirements/REQ-test/rtm-accepting.yml

# 5. 测试覆盖度 >= 80% 时通过门禁（预期门禁不拦截 rate >= 0.8）
```

---

**t10-rtm-reader** - RTM 快速读取接口  
phase: implement | side: backend | depends_on: [t1-schema-types]

**实施方案**：
1. 创建 `src/domain/rtm/reader.ts`，实现 `readRTM()` 函数：
   - `readRTM(requirementId: string, stage: Stage): RTMFile | null`
   - 读取 `docs/requirements/{requirementId}/rtm-{stage}.yml`
   - 使用 `js-yaml` 解析 YAML
   - 返回解析后的 RTM 对象（metadata/inputs/outputs/traceability/coverage）
   - 文件不存在或解析失败时返回 null（不抛错）
2. 支持所有节点：lifecycle / brainstorming / design / decomposing / implementing / accepting
3. 性能目标：< 10ms（vs 实时解析文档 > 500ms）

**验收标准**：
```bash
# 1. 读取 RTM 文件成功
node -e "
  const { readRTM } = require('./dist/domain/rtm/reader.js');
  const rtm = readRTM('REQ-test', 'design');
  console.log(rtm?.metadata?.stage);
"  # 期望: "design"

# 2. 性能 < 10ms
time node -e "
  const { readRTM } = require('./dist/domain/rtm/reader.js');
  const rtm = readRTM('REQ-test', 'design');
  console.log(rtm.coverage.design.rate);
"  # 期望: real < 0.01s

# 3. 文件不存在时返回 null
node -e "
  const { readRTM } = require('./dist/domain/rtm/reader.js');
  const rtm = readRTM('REQ-nonexistent', 'design');
  console.log(rtm === null ? 'PASS' : 'FAIL');
"  # 期望: PASS
```

---

### 第四批：工具集成与测试（依赖第三批）

**t11-status-tool-integration** - StatusTool 集成覆盖度  
phase: implement | side: backend | depends_on: [t10-rtm-reader]

**实施方案**：
1. 修改 `src/tools/StatusTool/StatusTool.ts`，返回覆盖度统计：
   - 读取当前需求的 RTM 文件（`readRTM(requirementId, currentStage)`）
   - 提取 `coverage` 字段（design / implementation / testing）
   - 添加到 `reqboard_status` 返回结果中：
     ```typescript
     {
       ...existingFields,
       fr_coverage: {
         design: { total, covered, rate, uncovered },
         implementation: { total, covered, rate, uncovered },
         testing: { total, covered, rate, uncovered }
       }
     }
     ```
2. 如果 RTM 文件不存在，返回 null

**验收标准**：
```bash
# 1. reqboard_status 返回覆盖度
curl http://localhost:13080/api/pmboard/status?requirementId=REQ-test \
  | jq '.fr_coverage.design.rate'
# 期望: 数值（如 1.0）

# 2. 覆盖度不足时显示缺口
curl http://localhost:13080/api/pmboard/status?requirementId=REQ-test \
  | jq '.fr_coverage.design.uncovered'
# 期望: ["FR-3"] 或 []

# 3. RTM 不存在时返回 null
curl http://localhost:13080/api/pmboard/status?requirementId=REQ-draft \
  | jq '.fr_coverage'
# 期望: null
```

---

**t12-e2e-test** - 端到端测试  
phase: test | side: fullstack | depends_on: [t7-rtm-decomposing, t8-rtm-implementing, t9-rtm-accepting, t11-status-tool-integration]

**实施方案**：
1. 创建测试脚本 `tests/rtm-e2e.test.ts`：
   - 创建测试需求（`reqboard_create`）
   - 提交需求文档（`reqboard_submit(kind=requirement)`）
   - 提交设计文档（`reqboard_submit(kind=design)`）
   - 批准拆分计划（`reqboard_submit(kind=plan)` + `reqboard_ask_confirm(target=plan)`）
   - 任务汇报（`reqboard_task_report`）
   - 提交验收材料（`reqboard_submit(kind=verification)`）
   - 验证所有 7 个 RTM 文件生成
   - 验证追溯链完整（fr_to_design / design_to_tasks / task_to_tests）
   - 验证覆盖度统计正确
2. 使用 vitest 运行测试

**验收标准**：
```bash
# 1. E2E 测试通过
cd packages/web/dsh-pmboard && pnpm test tests/rtm-e2e.test.ts
# 期望: PASS

# 2. 所有 7 个 RTM 文件生成
ls docs/requirements/REQ-test-e2e/rtm-*.yml | wc -l
# 期望: 7

# 3. 追溯链完整
grep "fr_to_design:" docs/requirements/REQ-test-e2e/rtm-design.yml
grep "design_to_tasks:" docs/requirements/REQ-test-e2e/rtm-decomposing.yml
grep "task_to_tests:" docs/requirements/REQ-test-e2e/rtm-accepting.yml

# 4. 覆盖度门禁正常工作（测试用例中验证覆盖度不足时拒绝提交）
```

---

**t13-performance-test** - 性能测试  
phase: test | side: backend | depends_on: [t10-rtm-reader]

**实施方案**：
1. 创建性能测试脚本 `tests/rtm-performance.test.ts`：
   - 测试 `readRTM()` 读取耗时（目标 < 10ms）
   - 对比实时解析文档耗时（预期 > 500ms）
   - 验证性能提升 250x
2. 使用 benchmark.js 或 vitest bench

**验收标准**：
```bash
# 1. RTM 读取性能 < 10ms
time node -e "
  const { readRTM } = require('./dist/domain/rtm/reader.js');
  for (let i = 0; i < 100; i++) {
    readRTM('REQ-test', 'design');
  }
"  # 期望: real < 1s（平均 < 10ms）

# 2. 实时解析性能 > 500ms
time node -e "
  const fs = require('fs');
  const content = fs.readFileSync('docs/requirements/REQ-test/requirement.md', 'utf-8');
  const frs = content.match(/\*\*FR-\d+:/g);
  console.log(frs.length);
"  # 期望: real > 0.5s

# 3. 性能提升比例 > 250x（(实时解析耗时 / RTM 读取耗时) > 250）
```

---

**t14-documentation** - 文档更新  
phase: doc | side: doc | depends_on: [t12-e2e-test, t13-performance-test]

**实施方案**：
1. 更新 `packages/web/dsh-pmboard/README.md`：
   - 添加 RTM YAML 功能说明
   - 添加使用示例（如何读取 RTM、查看追溯链）
2. 添加 `docs/architecture/rtm-infrastructure.md`（架构文档）：
   - RTM 触发点机制
   - 追溯链构建流程
   - 覆盖度门禁规则
3. 添加 `docs/guides/rtm-usage-guide.md`（使用指南）：
   - 如何在文档中添加标注（`<!-- serves: FR-X -->`）
   - 如何查看覆盖度统计
   - 如何解读 RTM 文件

**验收标准**：
```bash
# 1. README 包含 RTM 说明
grep "RTM YAML" packages/web/dsh-pmboard/README.md

# 2. 架构文档存在
test -f docs/architecture/rtm-infrastructure.md && echo "PASS" || echo "FAIL"

# 3. 使用指南存在
test -f docs/guides/rtm-usage-guide.md && echo "PASS" || echo "FAIL"

# 4. 使用指南包含标注示例
grep "<!-- serves:" docs/guides/rtm-usage-guide.md
```

---

## 任务依赖图

```
第一批（并行）:
  t1-schema-types ─┬─> t2-ledger-migration
                   ├─> t3-doc-parser
                   └─> t10-rtm-reader

第二批（依赖第一批）:
  t3-doc-parser ───> t4-traceability ───> t5-coverage-calculator ───> t6-coverage-gate
  
第三批（依赖第二批）:
  t4-traceability ─┬─> t7-rtm-decomposing ───> t8-rtm-implementing ───> t9-rtm-accepting
  t5-coverage-calculator ─┘

第四批（依赖第三批）:
  t10-rtm-reader ───> t11-status-tool-integration ─┬─> t12-e2e-test ───> t14-documentation
  t7-rtm-decomposing ─────────────────────────────┤
  t8-rtm-implementing ────────────────────────────┤
  t9-rtm-accepting ───────────────────────────────┘
  
  t10-rtm-reader ───> t13-performance-test ───> t14-documentation
```

---

## 批次计划

- **Batch 1**（并行，3 天）：t1 + t2 + t3 + t10
- **Batch 2**（串行，2 天）：t4 → t5 → t6
- **Batch 3**（串行，3 天）：t7 → t8 → t9
- **Batch 4**（并行，2 天）：t11 + t12 + t13 → t14

**总工期**：10 天

---

## 风险与缓解

### 风险 1：台账迁移失败导致数据损坏
- **概率**：低
- **影响**：高
- **缓解**：
  1. 迁移前自动备份（`dsh-reqboard.json.bak-v8`）
  2. 迁移脚本幂等（可重复运行）
  3. 增加回滚命令（`cp dsh-reqboard.json.bak-v8 dsh-reqboard.json`）

### 风险 2：覆盖度门禁过严导致工作流卡顿
- **概率**：中
- **影响**：中
- **缓解**：
  1. 门禁错误信息包含清晰的缺口清单（`uncovered` 字段）
  2. 测试覆盖度阈值设为 80%（非 100%），允许一定灵活性
  3. 提供"跳过门禁"的管理员接口（紧急情况使用）

### 风险 3：RTM 生成失败不被发现
- **概率**：低
- **影响**：中
- **缓解**：
  1. RTM 失败只记 warning，不打断主流程（FR-9）
  2. 集成 `rtm-health.ts` 健康检查
  3. `reqboard_status` 显示 RTM 健康状态

### 风险 4：文档标注格式不统一
- **概率**：中
- **影响**：低
- **缓解**：
  1. 提供清晰的使用指南（`docs/guides/rtm-usage-guide.md`）
  2. DocumentParser 支持多种格式（逗号分隔、带/不带空格）
  3. 提供 linter 工具检查标注格式

---

## 验收总览

完成标志：
1. ✅ 创建测试需求，生成所有 7 个 RTM 文件
2. ✅ 追溯链完整（fr_to_design / design_to_tasks / task_to_tests）
3. ✅ 覆盖度门禁正常工作（设计 100%、实施 100%、测试 ≥80%）
4. ✅ RTM 读取性能 < 10ms
5. ✅ 现有 77 个需求和 465 个任务迁移成功，schemaVersion 9
6. ✅ E2E 测试通过
7. ✅ 文档完整（架构文档 + 使用指南）
