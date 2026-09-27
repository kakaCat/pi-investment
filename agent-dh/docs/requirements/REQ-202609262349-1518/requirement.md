# REQ-202609262349-1518: RTM YAML 追溯基础设施完整实现

## 边界

### 做什么

1. **实现 RTM YAML 文件结构**：7 个文件（rtm-lifecycle.yml / rtm-brainstorming.yml / rtm-design.yml / rtm-decomposing.yml / rtm-implementing.yml + rtm-implementing/*.yml / rtm-accepting.yml），作为台账的派生数据，提供快速查询能力（~2ms）

2. **扩展台账数据模型**：需求对象新增 `artifacts[]` 字段（产物列表），任务对象新增 `designServes[]`（服务的 FR）和 `implements`（实现的设计章节）字段，schemaVersion 8 → 9，向后兼容

3. **实现 RTM 生成与追溯**：在 7 个触发点（立项、提交需求、确认需求、提交设计、确认设计、批准计划、任务状态变更）自动生成/更新 RTM；解析文档中的 `<!-- serves: FR-N -->` / `<!-- implements: design/xxx -->` / `<!-- covers: t-xxx -->` 标注，构建三级追溯链；计算覆盖度并作为门禁（设计 100%、实施 100%、测试 ≥80%）

### 不做什么

1. **不实时同步**：RTM 是快照模式（版本号标记），不做台账到 RTM 的实时双向同步

2. **不自动合并冲突**：多 Agent 并发修改同一 RTM 时，后写覆盖前写（文件级锁）

3. **不改变现有工具接口**：`reqboard_create`, `reqboard_submit` 等工具的输入输出保持不变，RTM 生成是内部逻辑

### 边界理由

- **轻量级集成**：RTM 作为性能优化层（250x 提升），不破坏现有架构
- **职责分离**：台账是唯一事实来源，RTM 是可重新生成的派生数据
- **向后兼容**：新字段可选，旧需求/任务继续工作

---

## 产品定义

### 一句话目标

为需求流水线补全 RTM YAML 追溯基础设施，使 Dive 模式能以 ~2ms 读取节点状态和追溯关系（250x 性能提升），并通过覆盖度门禁保证质量。

### 核心价值

1. **性能提升 250x**：从实时解析文档（~500ms）到读取 RTM 缓存（~2ms）
2. **质量保证**：覆盖度门禁（设计 100%、实施 100%、测试 ≥80%）拦截不完整的提交
3. **完整追溯**：快速回答"FR-X 对应哪些设计/任务/测试"（三级追溯链）

### 使用场景

1. **Dive 模式自动决策**：读取当前节点 RTM，2ms 内判断下一步动作（是否可以推进）
2. **用户查看追溯**：在 StageOverview 点击"追溯 Tab"，看到完整的 FR → 设计 → 任务 → 测试链
3. **门禁检查**：提交设计/计划/验收时，自动检查覆盖度，不足时拒绝并返回缺口清单

---

## 用户与角色

### 主要用户

1. **Dive 模式（AI Agent）**
   - 需要：快速读取节点状态、追溯关系、覆盖度统计
   - 使用：每次决策循环读取 RTM（~2ms），判断是否可以推进到下一节点

2. **需求执行窗口（AI Agent）**
   - 需要：在各个节点自动生成和更新 RTM
   - 使用：调用 reqboard 工具时自动触发 RTM 生成

3. **前端用户（人类）**
   - 需要：查看需求的完整追溯链和覆盖度
   - 使用：在 StageOverview 点击"追溯 Tab"，查看 FR → 设计 → 任务 → 测试的完整映射

4. **Reqboard 工具系统（后端）**
   - 需要：在 7 个触发点自动生成/更新 RTM，并执行覆盖度门禁检查
   - 使用：reqboard_submit / reqboard_ask_confirm / reqboard_task_move 等工具内部调用 RTM 生成逻辑

---

## 功能点

- **FR-1: RTM 文件结构设计**

实现 7 个 RTM YAML 文件（rtm-lifecycle.yml / rtm-brainstorming.yml / rtm-design.yml / rtm-decomposing.yml / rtm-implementing.yml + rtm-implementing/*.yml / rtm-accepting.yml），每个文件包含 metadata（版本、更新时间）、inputs（上游节点输出）、outputs（本节点产出）、traceability（追溯映射）、coverage（覆盖度统计）结构。

- **FR-2: 台账数据模型扩展**

需求对象新增 `artifacts[]` 字段（kind / path / stage / confirmed / confirmedAt），任务对象新增 `designServes[]`（字符串数组，如 ["FR-1", "FR-2"]）和 `implements`（字符串，如 "design/arch#1.1"）字段，schemaVersion 从 8 升到 9，新字段可选（缺省空数组/null），向后兼容。

- **FR-3: RTM 生成逻辑（7 个触发点）**

在立项（reqboard_create）、提交需求文档（reqboard_submit kind=requirement 门禁通过后）、确认需求（reqboard_ask_confirm kind=requirement）、提交设计文档（reqboard_submit kind=design 门禁通过后）、确认设计（reqboard_ask_confirm kind=design）、批准拆分计划（reqboard_ask_confirm target=plan）、任务状态变更（reqboard_task_move）时自动生成/更新对应节点的 RTM 文件。

- **FR-4: 文档标注解析**

解析 requirement.md / design/*.md / decomposition.md / tasks/*.md / test-cases.md 中的行内注释标注：`<!-- serves: FR-1, FR-2 -->`（该章节/任务服务哪些需求）、`<!-- implements: design/arch#1.1 -->`（该任务实现哪个设计章节）、`<!-- covers: t-354ea0 -->`（该测试用例覆盖哪个任务），支持逗号分隔的多值。

- **FR-5: 追溯关系索引**

构建三级追溯链：fr_to_design（需求 FR-N → 设计章节 design/xxx#N.N，在 design 阶段从设计文档的 serves 标注构建）、design_to_tasks（设计章节 → 任务 t-xxx，在 decomposing 阶段从拆分计划文档的 implements 标注和台账任务字段构建）、task_to_tests（任务 → 测试用例 TC-N，在 accepting 阶段从测试文档的 covers 标注构建），写入对应节点的 RTM 文件 traceability 字段。

- **FR-6: 覆盖度统计**

计算三种覆盖度：设计覆盖度（covered_frs / total_frs，有设计章节服务的 FR 数 / FR 总数）、实施覆盖度（covered_designs / total_designs，有任务实现的设计章节数 / 设计章节总数）、测试覆盖度（tested_tasks / total_tasks，有测试用例覆盖的任务数 / 任务总数），写入对应节点的 RTM 文件 coverage 字段。

- **FR-7: 覆盖度门禁**

在 reqboard_submit(kind=design) 时检查设计覆盖度必须 100%，在 reqboard_submit(kind=plan) 时检查实施覆盖度必须 100%，在 reqboard_submit(kind=verification) 时检查测试覆盖度必须 ≥80%，不足时拒绝提交并返回错误（包含 uncovered 清单：缺少设计的 FR / 缺少任务的设计章节 / 缺少测试的任务）。

- **FR-8: RTM 快速读取接口**

提供内部工具函数 `readRTM(requirementId, stage)`，读取指定需求的指定节点 RTM 文件，返回解析后的 JSON 对象（metadata / inputs / outputs / traceability / coverage），读取耗时 ~2ms（vs 实时解析文档 ~500ms）。

- **FR-9: 数据迁移工具**

提供迁移脚本 `scripts/migrate-reqboard-schema-v9.ts`，为现有 77 个需求和 465 个任务回填新字段（artifacts 初始化空数组，designServes/implements 初始化 null），支持增量迁移（只处理 schemaVersion < 9 的数据）和回滚（保留备份文件 dsh-reqboard.json.bak-v8）。

---

## 接口设计

### RTM 文件读取接口

**函数签名**：
```typescript
function readRTM(requirementId: string, stage: Stage): RTMFile | null
```

**输入**：
- `requirementId`: 需求 ID（如 "REQ-202609262349-1518"）
- `stage`: 节点名称（"lifecycle" | "brainstorming" | "design" | "decomposing" | "implementing" | "accepting"）

**输出**：
- 成功：返回解析后的 RTM 对象（包含 metadata / inputs / outputs / traceability / coverage）
- 失败：返回 null（文件不存在或解析失败）

**错误语义**：
- 文件不存在：返回 null（不抛错）
- YAML 解析失败：返回 null 并记录日志

### 覆盖度门禁接口

**集成点**：`reqboard_submit` 工具内部

**输入**：kind=design / plan / verification

**输出**：
- 覆盖度足够：正常返回（继续生成 RTM）
- 覆盖度不足：抛错（`COVERAGE_INSUFFICIENT`），错误对象包含：
  - `kind`: "design" | "implementation" | "testing"
  - `rate`: 当前覆盖度（如 0.67）
  - `threshold`: 要求阈值（1.0 或 0.8）
  - `uncovered`: 缺口清单（FR / 设计章节 / 任务的 ID 数组）

---

## 数据契约

### 需求对象新增字段

```typescript
interface Requirement {
  // ... 现有字段 ...
  artifacts?: Artifact[]  // 产物列表（可选，默认空数组）
}

interface Artifact {
  kind: "requirement" | "design" | "plan" | "verification" | "archive"
  path: string            // 文件路径（工作区相对）
  stage: string           // 节点名称
  confirmed?: boolean     // 是否已确认
  confirmedAt?: number    // 确认时间戳（ms）
}
```

### 任务对象新增字段

```typescript
interface Task {
  // ... 现有字段 ...
  designServes?: string[]  // 服务的 FR 列表（可选，如 ["FR-1", "FR-2"]）
  implements?: string      // 实现的设计章节（可选，如 "design/arch#1.1"）
}
```

### 台账 schemaVersion

```typescript
interface Ledger {
  schemaVersion: 9  // 从 8 升到 9
  // ...
}
```

### 字段约束

- `artifacts`: 可选，默认 `[]`，旧需求缺失时读取为空数组
- `designServes`: 可选，默认 `null`，旧任务缺失时读取为 null
- `implements`: 可选，默认 `null`，旧任务缺失时读取为 null
- 向后兼容：schemaVersion 8 的数据可以正常读取（缺失字段视为默认值）

---

## 迁移与兼容

### 迁移路径

1. **备份现有台账**：`cp dsh-reqboard.json dsh-reqboard.json.bak-v8`
2. **运行迁移脚本**：`node scripts/migrate-reqboard-schema-v9.ts`
3. **自动处理**：
   - 遍历所有需求，添加 `artifacts: []`（如果缺失）
   - 遍历所有任务，添加 `designServes: null`, `implements: null`（如果缺失）
   - 更新 `schemaVersion: 9`
4. **增量迁移**：只处理 `schemaVersion < 9` 的数据（幂等）

### 回滚方案

```bash
# 恢复备份
cp dsh-reqboard.json.bak-v8 dsh-reqboard.json

# 重启服务
./scripts/restart-with-build.sh
```

### 兼容性保证

- **新代码读旧数据**：缺失字段视为默认值（`artifacts: []`, `designServes: null`, `implements: null`）
- **旧代码读新数据**：忽略未知字段（JSON 解析不会报错）
- **RTM 文件向后兼容**：增加 `version` 字段，支持多版本 schema

---

## 验收标准

### 可执行判定命令

**1. 创建测试需求，生成所有 7 个 RTM 文件**

```bash
# 在测试窗口立项
reqboard_create(title="RTM 测试需求", category="feature")

# 验证 rtm-lifecycle.yml 已生成
ls docs/requirements/REQ-xxx/rtm-lifecycle.yml

# 提交需求文档并确认
reqboard_submit(kind=requirement)
reqboard_ask_confirm(kind=requirement)

# 验证 rtm-brainstorming.yml 已生成
ls docs/requirements/REQ-xxx/rtm-brainstorming.yml
grep "FR-1" docs/requirements/REQ-xxx/rtm-brainstorming.yml

# 提交设计文档并确认
reqboard_submit(kind=design)
reqboard_ask_confirm(kind=design)

# 验证 rtm-design.yml 已生成
ls docs/requirements/REQ-xxx/rtm-design.yml
grep "fr_to_design" docs/requirements/REQ-xxx/rtm-design.yml

# 批准拆分计划
reqboard_submit(kind=plan)
reqboard_ask_confirm(target=plan)

# 验证 rtm-decomposing.yml 和 rtm-implementing.yml 已生成
ls docs/requirements/REQ-xxx/rtm-decomposing.yml
ls docs/requirements/REQ-xxx/rtm-implementing.yml
ls docs/requirements/REQ-xxx/rtm-implementing/t-*.yml

# 提交验收材料
reqboard_submit(kind=verification)

# 验证 rtm-accepting.yml 已生成
ls docs/requirements/REQ-xxx/rtm-accepting.yml
grep "task_to_tests" docs/requirements/REQ-xxx/rtm-accepting.yml
```

**2. 覆盖度门禁检查**

```bash
# 提交设计文档但覆盖度不足（故意缺少某个 FR 的设计）
# 预期：拒绝提交，返回 uncovered: ["FR-3"]
reqboard_submit(kind=design)
# 输出应包含：COVERAGE_INSUFFICIENT, rate: 0.67, uncovered: ["FR-3"]

# 补充设计后再提交
# 预期：门禁通过，正常生成 rtm-design.yml
```

**3. 追溯链完整性验证**

```bash
# 读取 rtm-design.yml
cat docs/requirements/REQ-xxx/rtm-design.yml

# 验证 fr_to_design 映射存在
# 预期：FR-1 → ["design/arch#1.1", "design/arch#1.2"]

# 读取 rtm-decomposing.yml
cat docs/requirements/REQ-xxx/rtm-decomposing.yml

# 验证 design_to_tasks 映射存在
# 预期：design/arch#1.1 → ["t-354ea0"]

# 读取 rtm-accepting.yml
cat docs/requirements/REQ-xxx/rtm-accepting.yml

# 验证 task_to_tests 映射存在
# 预期：t-354ea0 → ["TC-1", "TC-2"]
```

**4. 性能验证**

```bash
# 测试 RTM 读取性能
time node -e "
  const { readRTM } = require('./packages/web/dsh-pmboard/src/rtm-reader');
  const rtm = readRTM('REQ-xxx', 'design');
  console.log(rtm.coverage.design.rate);
"
# 预期：real < 0.01s（~2ms）

# 对比实时解析文档性能
time node -e "
  const fs = require('fs');
  const content = fs.readFileSync('docs/requirements/REQ-xxx/requirement.md', 'utf-8');
  const frs = content.match(/\*\*FR-\d+:/g);
  console.log(frs.length);
"
# 预期：real > 0.5s（~500ms）
```

**5. 数据迁移验证**

```bash
# 运行迁移脚本
node scripts/migrate-reqboard-schema-v9.ts

# 验证 schemaVersion 已更新
jq '.schemaVersion' .dsh-data/dsh-reqboard.json
# 预期：9

# 验证新字段已添加
jq '.requirements[0].artifacts' .dsh-data/dsh-reqboard.json
# 预期：[]

jq '.tasks[0].designServes' .dsh-data/dsh-reqboard.json
# 预期：null

# 验证备份文件存在
ls .dsh-data/dsh-reqboard.json.bak-v8
```

---

## 判定标准

✅ **完成标志**：
1. 创建一个测试需求，生成所有 7 个 RTM 文件（lifecycle / brainstorming / design / decomposing / implementing / accepting）
2. 所有 RTM 文件包含完整的 metadata / inputs / outputs / traceability / coverage 结构
3. 覆盖度门禁正常工作（设计 100%、实施 100%、测试 ≥80%，不足时拒绝提交）
4. 三级追溯链完整（fr_to_design / design_to_tasks / task_to_tests）
5. RTM 读取性能 < 10ms（vs 实时解析 > 500ms）
6. 现有 77 个需求和 465 个任务迁移成功，schemaVersion 9

❌ **不合格标志**：
- RTM 文件缺失或结构不完整
- 覆盖度门禁未生效（允许不足的提交通过）
- 追溯链断裂（某级映射缺失）
- 性能未达标（读取 > 10ms）
- 数据迁移失败（台账损坏或新字段缺失）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |
| FR-7 | 🔴 **未被接收** | — |
| FR-8 | 🔴 **未被接收** | — |
| FR-9 | 🔴 **未被接收** | — |

> 🔴 **未被接收（9 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7、FR-8、FR-9

<!-- reqboard:marks:end -->
