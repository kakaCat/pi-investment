# REQ-99b58f: 修复 PM 插件生命周期流程（文档+代码）

## 1. 需求概述

### 1.1 背景
PM 插件的生命周期节点在 `docs/architecture/workflow-stages.md` 有权威定义（7 节点：立项 / 需求分析 / 技术设计 / 拆分 / 实施 / 验收 / 归档），但若干环节与定义不一致：
- 需求分析（`brainstorming`）缺少需求编号规范与文档规范检查
- 技术设计（`planning`）的产物定义不清（应为一套 `design/` 文档集，按分类伸缩）
- 拆分（`decomposing`）缺少 decomposition.md 对照清单
- 实施（`implementing`）：`todo` 是内存态（无持久化载体），且执行顺序有误（先 testing 后 in_review，应为先 Code Review 后测试）
- 验收（`accepting`）缺少版本化逐项验收单
- 需求创建后缺少提示词级别的引导

### 1.2 目标
修复 PM 插件的 7 个阶段流程定义，使其符合完整的软件开发生命周期规范。

### 1.3 范围
- 文档更新：`docs/architecture/reqboard-*.md`、`docs/rfcs/014-requirement-board.md`
- 状态机：**需求状态集不变**（7 节点 + legacy done，技术设计落在 `planning`）；任务状态调整（`todo` 内存态 → task 文件持久化 + `pending` 初始态；执行顺序 `in_review` 前置于 `testing`）
- 代码修改：类型定义、用例层、工具层、阶段提示词

---

## 1.4 生命周期总览

### 完整流程图

```
用户："帮我实现一个登录功能"
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 1：立项（draft）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ↓ Hook 捕获
  ↓ 两问确认（需求名称 + 类型）
  ↓ reqboard_create
  ↓ R1 自动推进
  
  状态：brainstorming（需求分析）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 2：需求分析（brainstorming）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  做什么：
  ✓ 澄清需求（与用户对话，九步检查表）
  ✓ 撰写需求文档 requirement.md
    - 功能需求：FR-1, FR-2, FR-3...
    - 非功能需求：NFR-1, NFR-2...
    - 验收标准：AC-1.1, AC-1.2...
  
  产物：
  📄 requirement.md（带编号规范）
  
  校验：
  ✓ 功能需求有编号（FR-1/FR-2...）
  ✓ 验收标准有编号（AC-1.1/AC-1.2...）
  ✓ 无重复、无跳号
  
  出口门（人工门）：
  ✓ 需求文档确认（reqboard_ask_confirm / 看板一键确认）
  
  ↓ 人确认 → reqboard_move(to='planning')
  
  状态：planning（技术设计）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 3：技术设计（planning）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  做什么：
  ✓ 在代码层面回答"怎么做"
  ✓ 撰写一套技术设计文档（按主题分，放 design/ 目录）
  
  产物（份数由分类决定，见 FR-2）：
  📄 design/architecture.md（架构 / 数据层 / 设计模式 / 代码规范 / UI 实现与样式）
  📄 design/data-model.md（数据模型）
  📄 design/interfaces.md（接口定义）
  📄 design/test-cases.md（测试用例内容）
  📄 plan.md（实施计划文档：任务表，提交待人批准）
  
  校验：
  ✓ 该分类要求的 design 文档齐备（feature 4 份 / refactor 2 份 / 其余可 0 份）
  ✓ 根文档必填节齐备（BASE「边界」+ 类型 DELTA）
  
  出口门（人工门）：
  ✓ 计划批准（reqboard_ask_confirm target=plan / 看板「批准计划」）
  
  ↓ 人批准 → reqboard_submit(kind='plan') → reqboard_decompose
  
  状态：decomposing（拆分）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 4：拆分（decomposing）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  做什么：
  ✓ 对照需求 + 技术设计，盘点新增/修改/删除（接口/功能/文件，精确到模块）
  ✓ 工作流划分 + 工作量预估
  ✓ 任务卡创作（做什么 / 怎么做 / 可证伪验收标准 / 依赖）
  ✓ reqboard_decompose 落库任务 DAG
  
  产物：
  📄 decomposition.md（拆分清单：计划任务表 ↔ 落库任务 id 对照）
  📁 tasks/t-001.md ~ t-007.md（每任务自足任务卡，薄卡被代码级拒绝）
  
  R3 派生推进：
  ✓ 任务落库后 system 自动把状态 planning → decomposing
    （前置仍是人工门「计划已批准」；未批准时 decompose 被代码级拒绝）
  
  出口门（人工门）：
  ✓ 拆分确认（reqboard_ask_confirm kind=decomposition，防"批了 A 落库 B"）
  
  ↓ 人确认 → reqboard_move(to='implementing')
  
  状态：implementing（实施）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 5：实施（implementing）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  做什么：
  ✓ 照卡执行（开工先写 implementation.md：步骤/顺序/验证方式）
  ✓ reqboard_task_move(in_progress) 领任务卡全文
  ✓ 执行 → reqboard_task_report 汇报（files_changed 自动上浮）
  
  任务 workflow（FR-6，6 个业务状态）：
  
  t-001: 数据库表设计
    status: pending
      ↓ reqboard_task_move(to='in_progress')
    status: in_progress
      - 创建 migrations/001_create_users_table.sql
      - 创建 migrations/002_create_login_attempts_table.sql
      - 更新 docs/schema.md
      ↓ reqboard_task_move(to='in_review')（跳过 integrating）
    status: in_review      ← 先 Code Review
      - 提交 PR、处理 Review 意见
      ↓ 通过 → reqboard_task_move(to='testing')
    status: testing        ← 后测试
      - 运行单元/集成/E2E 测试
      ↓ 通过 → reqboard_task_move(to='done')
    status: done ✅
  
  t-002: 登录 API 开发
    status: pending
      ↓ in_progress
      ↓ integrating（前后端联调，可跳过）
      ↓ in_review
      ↓ testing
      ↓ done ✅
  
  ...（t-003 ~ t-007 类似）
  
  出口门：
  ✓ 全部任务 done → R2 派生推进（自动进验收）
  ✓ done 有凭证门（汇报 / 真实动作 / 非批量 / 构建新鲜度）
  
  ↓ R2 自动推进
  
  状态：accepting（验收）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 6：验收（accepting）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  做什么：
  ✓ reqboard_submit(kind=verification) 生成逐项验收单
  ✓ 人逐项裁决（通过 / 不通过+意见）
  ✓ 不通过项 → 打回 + 自动生成返工任务
  
  产物：
  📄 verification.md（逐项验收单：每任务验收标准 + 需求级标准，逐项带证据）
  （版本化 v1/v2…，历史进 sheetHistory）
  
  出口门（人工门）：
  ✓ 全过 → 「验收通过」→ 直接归档
  ✓ 有未过 → 打回实施（implementing）
  
  ↓ 人验收通过
  
  状态：archived（归档）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 7：归档（archived）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  做什么：
  ✓ reqboard_submit(kind=archive) 补材料
    （需求目录 / 文档清单 / 合并去向 merged_into / 索引条目 / 说明书更新点）
  ✓ merged_into 真实写入对应项目文档
  
  出口门（代码级必填项校验）：
  ✓ 材料齐（缺项被代码级拒绝）
  
  状态：archived ✅（终态；done 仅为历史兼容）
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
完成！ 🎉
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 关键节点汇总

> 节点名以 `docs/architecture/workflow-stages.md`（**唯一事实源**）为准：
> 立项 / 需求分析 / 技术设计 / 拆分 / 实施 / 验收 / 归档。

| 阶段 | 节点（状态） | 做什么 | 产物 | 出口门 | 自动推进 |
|---|---|---|---|---|---|
| **1. 立项** | `draft` | 两问确认 → reqboard_create | REQ 卡片 | - | **R1** ✅ |
| **2. 需求分析** | `brainstorming` | 谈清"要什么" + 写需求文档 | requirement.md | **人工门：需求文档确认** | - |
| **3. 技术设计** | `planning` | 写一套技术设计文档（`design/`）+ 实施计划 | design/*.md + plan.md | **人工门：计划批准** | **R3** ✅ |
| **4. 拆分** | `decomposing` | 盘点变更 + 任务卡创作 + 落库 DAG | decomposition.md + tasks/*.md | **人工门：拆分确认** | - |
| **5. 实施** | `implementing` | 照卡执行 + 完工汇报 | 交付物 + 完工记录 | 全部任务 done | **R2** ✅ |
| **6. 验收** | `accepting` | 逐项验收单 + 人逐项裁决 | verification.md | **人工门：验收通过** | - |
| **7. 归档** | `archived` | 补归档材料 + merged_into 真实写入 | 归档材料 | 材料齐（代码级校验） | - |

---

### 3 个自动推进（Rollup，派生规则）

- **R1**：`draft` + 窗口接手开工 → `brainstorming`（阶段 1 出口，无人工门）
- **R3**：`planning` + 已落库任务 → `decomposing`（阶段 3 出口）
  ⚠️ **前置是人工门「计划批准」**——未批准时 `reqboard_decompose` 被代码级拒绝，R3 不可能凭空触发
- **R2**：`implementing` + 全部未取消任务 done（≥1 个）→ `accepting`（阶段 5 出口，无人工门）

---

### 人工闸门（5 道）

| # | 转移 | 确认对象 | 确认方式 |
|---|---|---|---|
| 1 | `brainstorming → planning` | 需求文档 requirement.md | 看板一键确认 / reqboard_ask_confirm |
| 2 | `planning → decomposing` | 一套技术设计文档（+ 实施计划） | **批准计划**（reqboard_ask_confirm target=plan） |
| 3 | `decomposing → implementing` | 拆分清单 decomposition.md | 看板一键确认（防"批了 A 落库 B"） |
| 4 | `accepting → archived` | 逐项验收单 verification.md | **验收通过**（人逐项裁决） |
| 5 | archived 内 | 归档材料（目录/清单/合并去向/索引/说明书更新点） | 代码级必填项校验 |

---

## 2. 功能需求

### FR-1: 需求编号规范（阶段 2）

**功能描述**：需求文档必须使用强制编号规范，包括功能需求、非功能需求和验收标准。

**编号格式**：
- 功能需求：FR-1, FR-2, FR-3...
- 非功能需求：NFR-1, NFR-2, NFR-3...
- 验收标准：AC-1.1, AC-1.2, AC-2.1...（与功能需求关联）

**示例**：
```markdown
## 2. 功能需求

### FR-1: 用户名密码登录
用户可以使用用户名和密码登录系统。

**验收标准**：
- AC-1.1: 输入正确用户名和密码可成功登录
- AC-1.2: 密码错误提示"用户名或密码错误"
- AC-1.3: 用户名不存在提示"用户名或密码错误"

### FR-2: 手机号登录
...

## 3. 非功能需求

### NFR-1: 安全性
- 密码使用 bcrypt 加密存储
- 登录失败 3 次锁定 15 分钟
...
```

**验收标准**：
- AC-1.1: 需求文档包含功能需求编号（FR-1, FR-2...）
- AC-1.2: 需求文档包含非功能需求编号（NFR-1, NFR-2...）
- AC-1.3: 每个功能需求有对应的验收标准（AC-1.1, AC-1.2...）
- AC-1.4: 编号格式正确，无重复，无跳号
- AC-1.5: reqboard_submit 提交需求文档时自动校验编号规范

---

### FR-2: 技术设计文档集（阶段 3 · 技术设计 / `planning`）

**功能描述**：`planning`（技术设计）节点在代码层面回答"怎么做"，产物是**一套技术设计文档**（按主题分），并提交实施计划（`plan.md`）待人批准。

**产物位置**：`docs/requirements/<REQ>/design/`（**不是**需求根目录）

**分类差异化（可伸缩）**——由 `category-doc-sets.ts` 的 BASE + DELTA 两层结构定义：

| 分类 | 必填 design 文档 | 类型专属必填节（DELTA） |
|---|---|---|
| feature | `architecture.md`、`data-model.md`、`interfaces.md`、`test-cases.md` | 产品定义 / 用户与角色 / 功能点 |
| refactor | `architecture.md`、`migration.md` | 现状 / 目标结构 / 行为不变式 |
| bug | 无（并入修复方案产物） | 复现步骤 / 根因 / 回归 |
| spike | 无 | 待答问题 / 结论 |
| doc | 无 | 目标读者 / 大纲 |
| chore | 无 | 完成判据 |

**BASE（所有分类共同）**：根文档必填节「边界」——"不做什么"是范围纪律的唯一防线。

**文档职责**（feature 为例）：
- `design/architecture.md`：架构 / 数据层（是否改表、schema）/ 设计模式与框架选型 / 代码规范 / UI 实现与样式
- `design/data-model.md`：数据模型
- `design/interfaces.md`：接口定义（前后端契约）
- `design/test-cases.md`：测试用例内容（单元 / 集成 / E2E）

**出口门**：人工门——计划批准（`reqboard_ask_confirm` target=plan）。

**禁止**（W7 边界）：工作流划分 / 工作量预估（属拆分）；写实现代码；产出最终任务 DAG（任务卡在**拆分**阶段创作）。

**验收标准**：
- AC-2.1: 阶段 3 节点为 `planning`（技术设计），**不新增** `technical_design` 状态
- AC-2.2: 技术设计文档放在 `design/` 子目录（不是需求根目录）
- AC-2.3: 文档集按分类伸缩——feature 4 份 / refactor 2 份 / bug·spike·doc·chore 可 0 份
- AC-2.4: feature 的 `design/architecture.md` 含架构、数据层、设计模式、代码规范、UI 实现与样式
- AC-2.5: feature 的 `design/interfaces.md` 含接口契约定义
- AC-2.6: `design/test-cases.md` 覆盖所有功能需求（FR-1/FR-2...）
- AC-2.7: BASE 必填节「边界」在任何分类缺失时都被拒绝
- AC-2.8: 类型 DELTA 必填节缺失时被拒绝
- AC-2.9: 出口门为人工门「计划批准」，未批准时 `reqboard_decompose` 被代码级拒绝
- AC-2.10: 技术设计阶段禁止产出任务 DAG 与工作量预估

---

### FR-3: 智能提示词级别引导

**功能描述**：Agent 根据需求复杂度自动判断并推荐合适的提示词级别（基础/详细/专家），在每个阶段注入不同详细度的纪律提示。

**提示词级别**：

#### 3.1 基础级别
- **适用场景**：doc/chore 类型，预估 <3 天
- **提示特点**：只给必要步骤，假设 Agent 懂流程
- **示例**：
  ```
  当前阶段：brainstorming
  1. 撰写需求文档
  2. 提交
  3. 等待确认
  ```

#### 3.2 详细级别
- **适用场景**：feature/refactor 类型，预估 3-10 天
- **提示特点**：包含完整步骤、示例代码、注意事项
- **示例**：
  ```
  当前阶段：brainstorming
  
  1. 撰写需求文档：docs/requirements/REQ-xxx/requirement.md
     使用编号规范：FR-1, NFR-1, AC-1.1
     
     示例：
     ### FR-1: 用户名密码登录
     ...
  
  2. 提交需求文档：reqboard_submit(kind='requirement', ...)
  
  3. 等待人工确认
  ```

#### 3.3 专家级别
- **适用场景**：spike/架构级变更，预估 >10 天
- **提示特点**：最少提示，只给原则和规范
- **示例**：
  ```
  当前阶段：brainstorming
  按照需求分析规范撰写文档，注意使用 FR-1/NFR-1/AC-1.1 编号规范。
  ```

**判断逻辑**：
```typescript
function recommendPromptLevel(req: Requirement): PromptLevel {
  const categoryWeight = { doc: 1, chore: 1, bug: 2, feature: 3, refactor: 3, spike: 4 }
  const workloadScore = estimateWorkload(req.summary) // 关键词分析
  const techComplexity = analyzeTechStack(req.summary) // 技术栈复杂度
  const totalScore = categoryWeight + workloadScore + techComplexity
  
  if (totalScore <= 3) return 'basic'
  if (totalScore <= 6) return 'detailed'
  return 'expert'
}
```

**验收标准**：
- AC-3.1: reqboard_create 时自动判断提示词级别
- AC-3.2: 需求记录包含 `promptLevel` 字段（basic/detailed/expert）
- AC-3.3: doc/chore 类型推荐基础级别
- AC-3.4: feature/refactor 类型推荐详细级别
- AC-3.5: spike/架构类推荐专家级别
- AC-3.6: capture-section.ts 根据 promptLevel 生成不同详细度的阶段纪律
- AC-3.7: 提示词内容符合对应级别的详细度要求

---

### FR-4: 拆分（阶段 4 · `decomposing`）

**功能描述**：把技术设计转成可执行任务 DAG。这是**任务粒度与依赖的唯一定死点**（W7 边界：任务卡在本阶段创作，不在技术设计阶段）。

**阶段 3 vs 阶段 4 的区别**：

| 维度 | 阶段 3 技术设计（`planning`） | 阶段 4 拆分（`decomposing`） |
|---|---|---|
| **目的** | 确定**怎么做**（代码层面） | 确定**拆成哪些任务、按什么顺序** |
| **产物** | 一套技术设计文档（`design/*.md`）+ 实施计划 | `decomposition.md` + 任务卡 `tasks/t-xxx.md` |
| **粒度** | 模块 / 接口 / 数据层 | 任务卡级（每卡可独立执行验收） |
| **禁止** | 工作流划分 / 工作量预估 / 产出任务 DAG | 薄卡落库 / 与技术设计矛盾时二次创作 |

**活动**：
1. 对照需求 + 技术设计，盘点**新增 / 修改 / 删除**（接口 / 功能 / 文件，精确到模块）
2. 工作流划分 + 工作量预估
3. 任务卡四要素创作：做什么 / 怎么做（`implementation`）/ 可证伪验收标准 / 依赖
4. `reqboard_decompose` 落库任务 DAG

**产物**：
- `decomposition.md`：拆分清单（计划任务表 ↔ 落库任务 id 对照）
- `tasks/t-xxx.md`：每任务自足任务卡（**薄卡被代码级拒绝**）

**任务卡结构**（对齐 `reqboard_submit(kind=plan, tasks=[...])`）：

| 字段 | 说明 |
|---|---|
| `key` | 批次内引用键（如 t1；`depends_on` 用它引用） |
| `title` | 动词开头的任务标题（≤120 字符） |
| `description` | 任务说明（改哪些文件/接口） |
| `phase` | doc / ui / analysis / implement / test / review / merge |
| `side` | frontend / backend / fullstack / doc |
| `depends_on` | 依赖的计划内 key |
| `acceptance` | **可证伪**验收标准（跑什么、看到什么算过） |
| `implementation` | 实施方案（**必填**：改哪些文件、步骤、验证方式——拆分卡 ≠ 实施卡） |

**出口门**：人工门——拆分确认（`reqboard_ask_confirm` kind=decomposition）。

**禁止**：薄卡落库；与技术设计矛盾时**退回技术设计改计划**，不二次创作。

**验收标准**：
- AC-4.1: 阶段 4 节点为 `decomposing`（拆分）
- AC-4.2: 产物为 `decomposition.md` + 任务卡 `tasks/t-xxx.md`
- AC-4.3: 任务卡含四要素（做什么 / 怎么做 / 可证伪验收标准 / 依赖）
- AC-4.4: `implementation` 必填，缺失被代码级拒绝（拆分卡 ≠ 实施卡）
- AC-4.5: `acceptance` 可证伪（空话 / 无锚点被打回）
- AC-4.6: `depends_on` 用批次内 key 引用同批任务
- AC-4.7: 出口门为人工门「拆分确认」，防"批了 A 落库 B"
- AC-4.8: `reqboard_decompose` 只落库**已批准计划**的任务表（未批准被代码级拒绝）
- AC-4.9: 任务粒度在拆分阶段定死，技术设计阶段不得产出任务 DAG

---

### FR-5: 任务持久化（task 文件）

**功能描述**：任务以本地 Markdown 文件形式持久化存储（`tasks/t-xxx.md`），支持跨会话、依赖管理、状态追踪。

**核心概念**：
- **task** = 任务卡文件（`tasks/t-xxx.md`）
- **status** = 任务卡里的状态字段
- **没有 todo 状态**：任务创建后就是任务卡，status 初始为 pending

**任务卡结构**（`tasks/t-xxx.md`，front-matter + 正文）：
```markdown
---
id: t-001
title: 数据库表设计
requirement_id: REQ-99b58f
status: pending
phase: analysis
side: backend
depends_on: []
---

## 做什么
（任务说明）

## 怎么做（implementation，必填）
1. 创建 migrations/001_create_users_table.sql
2. 更新 docs/schema.md
3. 执行 migration

## 验收标准（可证伪）
- [ ] users 表存在
- [ ] 所有字段类型正确
- [ ] 索引已创建

## 完工记录
（reqboard_task_report 追加）
```

**关键特性**：
1. **持久化存储**：本地文件，会话结束不丢失
2. **依赖管理**：`depends_on`（上游任务 key，全部 done 才能开工）
3. **状态追踪**：status 字段记录当前状态
4. **跨会话**：任何窗口都能继续执行

**与 todo_write 的区别**：

| 维度 | todo_write（内存） | task 文件（持久化） |
|---|---|---|
| 存储方式 | 内存 | 本地文件 |
| 持久化 | ❌ 会话结束丢失 | ✅ 永久保存 |
| 依赖管理 | ❌ 不支持 | ✅ `depends_on`（DAG） |
| 跨会话 | ❌ 不可用 | ✅ 任意窗口可继续 |
| 状态追踪 | 简单（pending/in_progress/completed） | 完整（6 个状态） |
| 适用场景 | 会话内临时清单 | 正式项目任务管理 |

**创建时机**：
```
阶段 4：拆分（decomposing）
  ↓ 计划已批准（人工门「计划批准」）
  ↓ reqboard_decompose 落库任务 DAG
  
创建任务卡：
  - tasks/t-001.md（数据库表设计）
  - tasks/t-002.md（登录 API 开发）
  - tasks/t-003.md（前端登录页）
  ...
  
初始 status 都是 "pending"
```

**验收标准**：
- AC-5.1: reqboard_decompose 为每个任务创建任务卡（tasks/t-xxx.md）
- AC-5.2: 任务卡包含：id/title/requirement_id/status/phase/side/depends_on/implementation/acceptance
- AC-5.3: task 文件持久化存储，会话结束不丢失
- AC-5.4: 支持依赖管理（`depends_on` 全部 done 时才能开工）
- AC-5.5: status 字段初始值为 "pending"
- AC-5.6: implementation 来自 plan.md 的任务细化步骤
- AC-5.7: acceptance 来自 plan.md 的验收方式

---

### FR-6: 任务状态机（task.status 的值）

**功能描述**：任务文件的 status 字段支持完整的开发生命周期状态转移。

**重要说明**：
- ❌ **没有 todo 状态**：任务创建后就是 task 文件
- ❌ **没有 task 状态**：task 是文件，不是状态
- ✅ **6 个业务状态**：pending / in_progress / integrating / in_review / testing / done（另有 canceled）

**现状 vs 目标（本次改动点）**：

| 项 | 现状（代码实况） | 目标 |
|---|---|---|
| 载体 | 内存态 `todo`，会话结束丢失 | 任务卡持久化（`tasks/t-xxx.md`） |
| 初始状态 | `todo` | `pending` |
| 执行顺序 | in_progress → integrating → **testing** → **in_review** → done | in_progress → integrating → **in_review** → **testing** → done |
| 差异 | 先测试、后复核 | **先 Review、后测试** |

**完整状态机**（都是 task.status 的值）：
```
pending（待办）
  ↓ 开工
in_progress（执行中）
  ↓ 联调（可选）
integrating（联调中）——— 前后端分离需要
  ↓                   纯前端/后端跳过
in_review（审查中）
  ↓ 通过        ↓ 返工
testing       in_progress
  ↓ 通过    ↓ 失败
done      in_progress
```

**状态说明**：

#### 6.1 pending（待办）
- **含义**：任务已创建，等待开工
- **条件**：`depends_on` 全部 done（无依赖阻塞）
- **转移**：pending → in_progress（开工）

#### 6.2 in_progress（执行中）
- **含义**：正在编码/写文档
- **操作**：reqboard_task_move(task_id, to='in_progress')
- **转移**：
  - in_progress → integrating（需要联调）
  - in_progress → in_review（不需要联调）

#### 6.3 integrating（联调中，可选）
- **含义**：前后端联调、接口调试
- **条件**：前后端分离项目
- **跳过**：纯前端/纯后端/文档类任务
- **转移**：integrating → in_review（联调完成）

#### 6.4 in_review（审查中）
- **含义**：Code Review、提交 PR、处理意见
- **转移**：
  - in_review → testing（Review 通过）
  - in_review → in_progress（需要返工）

#### 6.5 testing（测试中）
- **含义**：单元测试、集成测试、E2E 测试
- **转移**：
  - testing → done（测试通过）
  - testing → in_progress（测试失败返工）

#### 6.6 done（完成）
- **含义**：测试通过，任务完成
- **终态**：不再转移

**状态转移示例**：
```json
// 1. 任务创建
{
  "id": "t-001",
  "status": "pending",
  "depends_on": []
}

// 2. 开工
reqboard_task_move(task_id='t-001', to='in_progress')
{
  "status": "in_progress",
  "execution_log": [
    { "time": "2026-01-15 10:00", "from": "pending", "to": "in_progress", "reason": "开始编码" }
  ]
}

// 3. 联调（可选）
reqboard_task_move(task_id='t-001', to='integrating')
{
  "status": "integrating",
  "execution_log": [
    ...,
    { "time": "2026-01-15 14:00", "from": "in_progress", "to": "integrating", "reason": "前后端联调" }
  ]
}

// 4. Review
reqboard_task_move(task_id='t-001', to='in_review')
{
  "status": "in_review"
}

// 5. 测试
reqboard_task_move(task_id='t-001', to='testing')
{
  "status": "testing"
}

// 6. 完成
reqboard_task_move(task_id='t-001', to='done')
{
  "status": "done",
  "files_changed": ["migrations/001_create_users_table.sql", "docs/schema.md"]
}
```

**验收标准**：
- AC-6.1: TaskStatus 类型包含 6 个业务状态：pending/in_progress/integrating/in_review/testing/done（另有 canceled）
- AC-6.1b: 执行顺序为 in_review → testing（先 Code Review、后测试）
- AC-6.2: 没有 todo 状态，没有 task 状态
- AC-6.3: reqboard_task_move 支持所有合法的状态转移
- AC-6.4: integrating 是可选状态（可跳过：in_progress → in_review）
- AC-6.5: 支持返工：in_review → in_progress
- AC-6.6: 支持返工：testing → in_progress
- AC-6.7: 状态转移写入 task 文件的 status 字段
- AC-6.8: 状态转移记录到 execution_log（时间/from/to/reason）
- AC-6.9: 每次状态转移都要求填写 reason

---

### FR-7: 验收文档生成（阶段 6）

**功能描述**：阶段 6 自动生成 verification.md 验收文档，包含验收列表、操作步骤、预期结果，替代当前只有弹框验收的做法。

**verification.md 结构**：
```markdown
# 验收文档

## 1. 验收列表

### FR-1: 用户名密码登录
**验收内容**：用户可以使用用户名和密码登录系统

**操作步骤**：
1. 打开登录页 http://localhost:3000/login
2. 输入用户名：testuser
3. 输入密码：Test123456
4. 点击"登录"按钮

**预期结果**：
- 登录成功
- 跳转到首页
- 显示用户信息

**实际结果**：
（待填写）

**验收状态**：⬜ 待验收

---

### FR-2: 手机号登录
...

## 2. 测试报告
- 单元测试：37/37 通过，覆盖率 85%
- 集成测试：5/5 通过
- E2E 测试：3/3 通过

## 3. 文档完整性检查
✓ requirement.md 存在
✓ technical-design.md 存在
✓ frontend-spec.md 存在
✓ backend-spec.md 存在
✓ ui-design.md 存在
✓ test-cases.md 存在
✓ plan.md 存在
✓ 所有任务有实施文档（tasks/t-001.md）
✓ 所有任务有测试报告
✓ reviews/ 目录非空
✓ tests/ 目录非空

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| FR-1 | 用户名密码登录 | ✓ 通过 | user | 2026-01-15 14:30 |
| FR-2 | 手机号登录 | ✓ 通过 | user | 2026-01-15 14:32 |
...

**验收结论**：全部通过 ✅
```

**验收流程**：
1. Agent 提交验收材料（reqboard_submit kind='verification'）
2. 后端自动生成 verification.md
3. 后端执行文档完整性检查
4. 后端生成验收单（从需求文档提取验收项）
5. Agent 调用 reqboard_accept_sheet 逐项验收
6. 用户操作验收（按操作步骤执行，确认预期结果）
7. 全部通过后更新 verification.md 的验收结果表

**验收标准**：
- AC-7.1: reqboard_submit(kind='verification') 自动生成 verification.md
- AC-7.2: verification.md 包含所有功能需求的验收项（FR-1/FR-2...）
- AC-7.3: 每个验收项包含操作步骤和预期结果
- AC-7.4: 自动执行文档完整性检查（检查 9 类文档）
- AC-7.5: 文档缺失时阻止验收并提示补充
- AC-7.6: reqboard_accept_sheet 弹框包含操作步骤
- AC-7.7: 验收完成后自动更新 verification.md 的验收结果表
- AC-7.8: 验收结果表包含：编号/验收项/状态/验收人/验收时间

---

## 3. 非功能需求

### NFR-1: 文档规范检查

**功能描述**：在关键节点自动检查文档规范，确保文档完整性和格式正确性。

**检查点**：

#### 3.1 需求文档检查（阶段 2 提交时）
- ✓ 功能需求有编号（FR-1, FR-2...）
- ✓ 非功能需求有编号（NFR-1, NFR-2...）
- ✓ 验收标准有编号（AC-1.1, AC-1.2...）
- ✓ 编号格式正确
- ✓ 无重复编号
- ✓ 无跳号
- ✓ 每个功能需求有至少一个验收标准

#### 3.2 技术设计文档检查（阶段 3 提交时）
- ✓ 该分类要求的 design 文档齐备（feature: architecture/data-model/interfaces/test-cases；refactor: architecture/migration）
- ✓ 根文档必填节齐备（BASE「边界」+ 类型 DELTA）
- ✓ `design/architecture.md` 含架构、数据层、设计模式、代码规范
- ✓ `design/interfaces.md` 含接口契约（请求/响应格式）
- ✓ `design/test-cases.md` 覆盖所有功能需求

#### 3.3 文档完整性检查（阶段 6 验收时）
- ✓ requirement.md 存在
- ✓ 该分类要求的 design 文档齐备
- ✓ 拆分产物存在（decomposition.md + tasks/t-xxx.md）
- ✓ 每个任务有完工记录（reqboard_task_report）
- ✓ 验收单 verification.md 已生成

**检查不通过的处理**：
- 阻止提交（reqboard_submit 返回错误）
- 返回具体的错误信息（缺失的编号、缺失的文档）
- Agent 根据错误信息补充文档后重新提交

**验收标准**：
- AC-N1.1: reqboard_submit(kind='requirement') 自动执行需求文档检查
- AC-N1.2: 检查不通过时返回错误并阻止提交
- AC-N1.3: 错误信息包含具体缺失内容
- AC-N1.4: reqboard_submit(kind='technical') 自动执行技术文档检查
- AC-N1.5: reqboard_submit(kind='verification') 自动执行文档完整性检查
- AC-N1.6: 文档完整性检查结果写入 verification.md

---

### NFR-2: 向后兼容性

**功能描述**：修复过程中保持向后兼容，已有需求和任务能够平滑迁移。

**兼容策略**：

#### 2.1 状态兼容
- 已有需求的状态（planning/decomposing/implementing）继续有效
- **需求状态集不变**（7 节点 + legacy done）——技术设计落在 `planning`，不新增 `technical_design`
- 状态转移规则不变（`planning → decomposing` 仍有效，前置人工门「计划批准」）

#### 2.2 任务状态兼容
- 已有任务状态（todo/in_progress/integrating/testing/in_review/done）继续有效，历史记录原样保留
- 新建任务使用 `pending` 初始态（替代内存 `todo` 作为持久化 task 文件的初始状态）
- 执行顺序调整向后兼容：旧记录中的 testing→in_review 顺序不改写；新任务按 in_review→testing 执行
- 允许从旧状态转移到新状态（in_progress → integrating → in_review）

#### 2.3 文档兼容
- 已有需求不强制要求 design 文档集
- 验收时检查文档完整性，缺失的文档只警告不阻止（存量在途需求）
- 新建需求按其分类强制要求 design 文档齐备（feature 4 份 / refactor 2 份 / 其余 0 份）

**数据迁移**：
- 不需要数据迁移（状态向后兼容）
- 工具层支持新旧两种状态
- 提示词根据需求创建时间判断使用新旧流程

**验收标准**：
- AC-N2.1: 已有需求状态不变，可以继续推进
- AC-N2.2: 已有任务状态不变，可以继续执行
- AC-N2.3: 新建需求仍用 7 节点（技术设计落在 `planning`，不新增状态）
- AC-N2.4: 新建任务使用 `pending` 初始态并落成 task 文件
- AC-N2.5: 已有需求验收时文档缺失只警告不阻止
- AC-N2.6: 新建需求验收时文档缺失阻止验收

---

## 4. 状态机变更

### 4.1 需求状态（RequirementStatus）

**修复前**（8 个状态）：
```
draft → brainstorming → planning → decomposing → implementing → accepting → archived → done
```

**修复后**（8 个状态，节点不变）：
```
draft → brainstorming → planning → decomposing → implementing → accepting → archived → done
```

**变更**：
- **需求状态不新增**——保持 7 节点 + legacy done；`planning` 即「技术设计」节点，不另立 `technical_design`
- 节点**内容**调整：`planning` 的产物从"计划文档"扩展为"一套技术设计文档（`design/`）+ 实施计划"
- 状态转移表不变

---

### 4.2 任务状态（TaskStatus）

**修复前**（现有代码实况 7 个状态：todo/in_progress/integrating/testing/in_review/done/canceled）：
```
todo → in_progress → integrating → testing → in_review → done
```
两点偏差：① `todo` 是**内存态**（会话结束丢失，无持久化载体）；② **testing 在 in_review 之前**（先生成测试证据、再等人复核）。

**修复后**（6 个业务状态 + canceled）：
```
pending → in_progress → integrating → in_review → testing → done
                            ↓ 返工        ↓ 返工
                       in_progress    in_progress
```

**变更**：
- `todo`（内存态）→ task 文件持久化，初始状态 `pending`
- **顺序调整**：`in_progress → integrating → testing → in_review → done` 改为 `in_progress → integrating → in_review → testing → done`
  （**先 Code Review、后测试**：Review 通过才进测试，测试通过才算完成）
- 保留返工路径（in_review/testing → in_progress）

---

## 5. 文档数量对比

### 5.1 现状（本需求提出时）
- 需求分析（`brainstorming`）：requirement.md
- 技术设计（`planning`）：plan.md（技术方案 + 任务表混写）
- 拆分（`decomposing`）：任务卡落库，无 decomposition.md 对照清单
- 验收（`accepting`）：弹框逐项验收，无版本化验收单
- **总计：2 份固定文档**

### 5.2 目标
- 需求分析（`brainstorming`）：requirement.md（编号规范）
- 技术设计（`planning`）：`design/` 文档集（feature 4 份 / refactor 2 份 / 其余 0 份）+ plan.md
- 拆分（`decomposing`）：decomposition.md + 任务卡 `tasks/t-xxx.md`
- 验收（`accepting`）：版本化验收单 verification.md
- **总计：按分类伸缩的 design 文档集 + 3 份固定文档 + 3 处规范检查**

---

## 6. 实施影响分析

### 6.1 影响范围

#### 文档更新
- docs/architecture/reqboard-stage-detail.md
- docs/architecture/workflow-stages.md
- docs/architecture/reqboard-doc-path-contract.md
- docs/rfcs/014-requirement-board.md

#### 代码修改
- packages/pages/dsh-pmboard/src/domain/requirement/RequirementStatus.ts
- packages/pages/dsh-pmboard/src/domain/task/TaskStatus.ts
- packages/pages/dsh-pmboard/src/application/use-cases/SubmitVerification.ts
- packages/pages/dsh-pmboard/src/application/use-cases/MoveTask.ts
- packages/pages/dsh-pmboard/src/application/use-cases/AcceptSheet.ts
- packages/pages/dsh-pmboard/src/application/internal/category-doc-sets.ts
- packages/pages/dsh-pmboard/src/application/internal/rollup.ts
- packages/pages/dsh-pmboard/src/domain/prompt/（阶段提示词注入）

### 6.2 风险点
- 存量在途需求的 design 文档缺失
- 文档规范检查可能阻止旧需求提交
- 任务状态执行顺序调整（`in_review` ↔ `testing`）需同步前端与阶段提示词

### 6.3 缓解措施
- 向后兼容设计（NFR-2）
- 旧需求文档检查只警告不阻止
- 分阶段部署（先文档后代码）

---

## 7. 验收总结

### 7.1 核心改进
1. **文档完整性**：技术设计文档集按分类伸缩（`design/` 目录）；验收产出版本化逐项验收单
2. **编号规范**：强制使用 FR-1/NFR-1/AC-1.1 编号
3. **技术设计**：落在 `planning` 节点（**不新增状态**），产物为一套 `design` 文档 + 实施计划
4. **任务透明**：任务状态从 3 个增加到 6 个；需求状态保持 8 个不变
5. **验收规范**：从弹框变成版本化逐项验收单
6. **规范检查**：3 处文档规范检查（需求 / 技术设计 / 验收）
7. **智能引导**：根据需求复杂度自动推荐提示词级别

### 7.2 验收清单
- [ ] FR-1: 需求编号规范（5 个验收标准）
- [ ] FR-2: 技术设计文档集（10 个验收标准）
- [ ] FR-3: 智能提示词级别引导（7 个验收标准）
- [ ] FR-4: 拆分（9 个验收标准）
- [ ] FR-5: 任务持久化（7 个验收标准）
- [ ] FR-6: 任务状态机（10 个验收标准）
- [ ] FR-7: 验收文档生成（8 个验收标准）
- [ ] NFR-1: 文档规范检查（6 个验收标准）
- [ ] NFR-2: 向后兼容性（6 个验收标准）

**总计：68 个验收标准**

---

## 8. 附录

### 8.1 术语表
- **PRD**：Product Requirement Document，产品需求文档
- **FR**：Functional Requirement，功能需求
- **NFR**：Non-Functional Requirement，非功能需求
- **AC**：Acceptance Criteria，验收标准
- **节点名**（权威定义见 `workflow-stages.md`）：立项 / 需求分析 / 技术设计 / 拆分 / 实施 / 验收 / 归档
- **状态标识**（代码）：draft / brainstorming / planning / decomposing / implementing / accepting / archived（+ legacy done）
- **实施计划**：`planning`（技术设计）节点提交的**文档名**（`plan.md`），**不是节点名**
- **task 文件**：任务以本地文件持久化（`tasks/t-xxx.md`，含 status/depends_on 等字段），区别于内存中的临时清单（todo_write）
- **task.status**：任务状态字段，取值 pending / in_progress / integrating / in_review / testing / done

### 8.2 参考文档
- **`docs/architecture/workflow-stages.md`**：流程节点**唯一事实源**（7 节点名 / 产物 / 出口门）
- `docs/architecture/reqboard-doc-path-contract.md`：产物路径契约
- `docs/rfcs/014-requirement-board.md`：PM 插件设计 RFC
- `docs/requirements/REQ-31e11f/requirement.md`：五道人工确认门定义
- `packages/pages/dsh-pmboard/src/application/internal/category-doc-sets.ts`：分类文档集（BASE + DELTA）
- `packages/pages/dsh-pmboard/src/domain/workflow/RollupSpec.ts`：R1/R2/R3 派生规则

---

**文档版本**: v1.0  
**创建时间**: 2026-01-XX  
**创建人**: Agent (investor, w-84d369f2)  
**需求状态**: brainstorming → 待确认
