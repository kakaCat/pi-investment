# pmboard 优化计划 - 完整开发流程

## 当前问题诊断

### 1. 缺少明确的人机回路
- 哪些阶段需要人确认？不清楚
- Agent 不知道什么时候该等人、什么时候继续

### 2. 缺少结构化文档生成
- 需求文档（requirements.md）- 缺
- 拆分方案（breakdown.md）- 缺
- 验收文档（verification.md）- 有但不够结构化

### 3. 缺少与 wiki 的集成
- Agent 不读 wiki（代码规范、架构文档）
- 讨论需求时不知道项目现状

### 4. 缺少具体开发阶段
- 联调（前后端接口调试）- 缺
- Review - 缺
- 测试 - 缺

## 优化方案

### Phase 1: 增强阶段定义和人机回路 ✅

#### 1.1 新增阶段
- `requirement-analysis` (需求分析) - 讨论需求，生成需求文档 → **人确认**
- `technical-design` (技术设计) - 拆解改动（接口/表/字段） → **人确认**
- `development` (开发)
- `integration` (联调) - 前后端接口调试
- `review` (代码审查)
- `testing` (测试)

#### 1.2 人机回路明确标注
每个阶段标注：
- 🤖 Auto: Agent 自动推进
- 👤 Human Gate: 需要人确认才能推进
- 🔄 Hybrid: Agent 做完后提醒人确认

#### 1.3 SystemPrompt 增强
根据阶段注入不同指引：
- requirement-analysis: "读取 wiki 了解项目规范，讨论需求并生成文档"
- technical-design: "列出要改动的接口、表、字段、数据处理"

### Phase 2: 结构化文档生成 ✅

#### 2.1 需求文档模板（requirement.md）
```markdown
# 需求：{title}

## 需求背景
为什么要做这个？

## 功能描述
要做什么？

## 涉及模块
- 前端：xxx 页面
- 后端：xxx 接口
- 数据库：xxx 表

## 非功能需求
- 性能要求
- 安全要求
- 兼容性

## 风险点
可能的问题
```

#### 2.2 技术设计文档（design.md）
```markdown
# 技术设计

## API 变更
### 新增接口
- POST /api/xxx

### 修改接口
- PUT /api/yyy

## 数据库变更
### 新增表
- table_name

### 修改表结构
- ALTER TABLE xxx ADD COLUMN yyy

### 数据迁移
- 历史数据如何处理

## 前端变更
- 新增页面
- 修改组件
```

#### 2.3 验收文档（verification.md）
```markdown
# 验收文档

## 功能清单
- [ ] 功能 A
- [ ] 功能 B

## 测试用例
1. 场景 1: 输入 X → 输出 Y
2. 场景 2: 边界条件

## 改动摘要
- 新增 3 个接口
- 修改 2 个页面
- 新增 1 个表

## 回归测试
- [ ] 不影响现有功能 A
- [ ] 不影响现有功能 B
```

### Phase 3: Wiki 集成 ✅

#### 3.1 需求分析阶段自动读取
- docs/architecture/xxx.md (架构文档)
- docs/guides/coding-standards.md (代码规范)
- docs/api/existing-apis.md (现有 API)

#### 3.2 SystemPrompt 注入 wiki 上下文
```
【需求分析阶段】
在讨论需求前，已为你准备：
- 项目架构：{architecture summary}
- 代码规范：{coding standards}
- 现有 API：{api list}

请基于以上背景讨论需求。
```

### Phase 4: 新增工具 ✅

#### 4.1 reqboard_generate_doc
自动生成结构化文档

#### 4.2 reqboard_read_wiki
读取 wiki 相关内容

#### 4.3 reqboard_overview
项目全景报告

## 实施步骤

### Step 1: 扩展状态机（1-2小时）
修改 `packages/pages/dsh-pmboard/src/shared/protocol.ts`
- 添加新状态
- 定义状态转换规则
- 标注人机回路

### Step 2: 增强 SystemPrompt（1小时）
修改 `packages/pages/dsh-pmboard/src/host/capture.ts`
- 为每个阶段定义指引文本
- 集成 wiki 读取

### Step 3: 新增文档生成工具（2-3小时）
在 `packages/pages/dsh-pmboard/src/host/agent-tools.ts`
- reqboard_generate_doc
- reqboard_read_wiki
- reqboard_overview

### Step 4: 优化 rollup 自动推进（1小时）
修改 `packages/pages/dsh-pmboard/src/host/rollup.ts`
- 根据人机回路决定是否自动推进

---

**开始实施？**
