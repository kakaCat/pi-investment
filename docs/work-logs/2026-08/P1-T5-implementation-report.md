# P1-T5 实施报告：前端「召回审计」Tab

**任务状态**: ✅ 前端实现完成，等待 P1-T4 后端部署后验收

**执行日期**: 2026-08-13

---

## 实施内容

### 1. API 层实现 (`web-frontend/src/services/api/memory.ts`)

追加了三个 API 函数和相关类型定义：

```typescript
// 类型定义
export interface RecallAuditHit { 
  memory_id, score, source, bm25_score?, vector_score?, 
  title?, content?, feedback?, feedback_by?, feedback_at?
}

export interface RecallAuditItem {
  id, ts, session_id?, flow, query_text?, strategy?, degraded?,
  gate_result, suppress_reason?, hits: RecallAuditHit[], created_at?
}

export interface RecallAuditStats {
  total, injected, suppressed, injection_rate,
  by_flow: {...}, suppress_reasons: {...}, score_histogram: [...]
}

// API 函数
export const recallAuditApi = {
  getAudit(params): Promise<{items, total}>    // GET /api/memory/recall-audit
  getStats(params): Promise<RecallAuditStats>  // GET /api/memory/recall-audit/stats
  postFeedback(auditId, body): Promise<any>    // POST /api/memory/recall-audit/{id}/feedback
}
```

**契约遵守**:
- ✅ apiClient 拦截器已解包 `{success,data}` 信封，函数直接返回解包后数据
- ✅ 字段名使用 snake_case（与后端 PG 表契约一致）
- ✅ 参照 `memory.ts` 现有函数模式实现

---

### 2. 召回审计页面 (`web-frontend/src/views/Memory/RecallAudit.vue`)

**功能实现**:

#### ① 统计卡片区域
- 四个指标卡片：总召回次数、注入次数、抑制次数、注入率
- 抑制原因分布标签云（`suppress_reasons` 对象展示）

#### ② 筛选栏
- **流程下拉框**: 全部/交互对话/技能调用/调度任务/唤醒事件
- **结果下拉框**: 全部/已注入/已抑制
- **日期范围选择器**: `date_from` 和 `date_to` 参数
- **仅抑制开关**: `suppressed_only` 布尔值
- **刷新按钮**: 重新加载列表和统计

#### ③ 审计列表（el-table）
- 可展开行，展开显示命中详情（hits）
- 列: 时间、流程、查询文本、结果、抑制原因、命中数、策略
- **suppressed 行样式**: 灰色背景（通过 `:deep(.suppressed-row)` 实现）

#### ④ 行展开 - 命中详情（hits）
- 每个 hit 显示：记忆 ID、source 标签、得分、BM25/向量分数
- **👍👎 反馈按钮**:
  - 调用 `postFeedback(auditId, {memory_id, feedback: 'relevant'|'irrelevant', feedback_by: 'human'})`
  - 本地状态更新（乐观 UI）
  - 409 冲突处理（agent 覆盖 human 被拒）
- 已标注状态显示：`feedback` 和 `feedback_by`

#### ⑤ 分页
- `el-pagination` 组件，支持切换页大小（20/50/100）

**样式处理**:
- ❌ 原使用 `@apply` 指令，导致 Tailwind CSS 编译错误
- ✅ 已修正为纯 CSS（避免 scoped style 中的 utility class 解析问题）

---

### 3. Memory 主页面集成 (`web-frontend/src/views/Memory/index.vue`)

- 添加 `el-tabs` 组件包裹原有内容
- 新增 `activeTab` 状态（默认 `'entries'`）
- 两个 tab:
  - `label="记忆条目" name="entries"`: 原有的记忆列表和调度观测
  - `label="召回审计" name="audit"`: 新的 `<RecallAudit />` 组件
- 导入 `RecallAudit.vue` 组件

---

## 验收状态

### ✅ 已完成验收项

1. **编译验证**:
   ```bash
   cd web-frontend && npm run build
   # ✓ built in 853ms（无错误）
   ```

2. **契约一致性**:
   - API 函数签名与 P1-T4 契约逐字一致
   - 字段名使用 snake_case（`memory_id`, `gate_result`, `suppress_reason` 等）
   - 筛选参数名与后端契约匹配（`flow`, `gate_result`, `date_from`, `date_to`, `suppressed_only`, `page`, `page_size`）

3. **代码质量**:
   - 无 TypeScript 类型错误
   - 使用 Element Plus 组件库（与项目现有风格一致）
   - 响应式数据管理（Vue 3 Composition API）

### ⏳ 待 P1-T4 部署后验收

根据任务契约：
> **禁止用 mock 数据充验收**。`cd web-frontend && npm run dev` 起页面真实截图；feedback 按钮点击后 PG 里 hits 对应元素有 `feedback_by:"human"`。

**当前状态**:
- P1-T4 commit `23f55d6` 在 `feat/P1-T4` 分支，**尚未合并 main**
- 生产 5001 端口尚未部署 P1-T4 路由
- PG 表 `quant.memory_recall_audit` 已创建（见下方）

**测试结果**:
```bash
$ curl -s "http://127.0.0.1:5001/api/memory/recall-audit?page=1&page_size=5"
# 返回 404（路由未注册）—— 预期行为，等待 P1-T4 部署
```

```bash
$ psql -d quant_investment -c "\d quant.memory_recall_audit"
# ✅ 表已存在，字段与契约一致（id, ts, session_id, flow, query_text, strategy, 
#    degraded, gate_result, suppress_reason, hits JSONB, created_at）
```

---

## 待 Claude 验收的操作步骤

### Step 1: 确认 P1-T4 已部署到 5001

```bash
# 检查 P1-T4 是否已合并并部署
curl -s "http://127.0.0.1:5001/api/memory/recall-audit?page=1&page_size=1" | python3 -m json.tool
# 预期：返回 {"items": [], "total": 0} 或有数据
```

### Step 2: 启动前端并截图

```bash
cd /Users/yunpeng/pi-investment/web-frontend
npm run dev
# 访问 http://127.0.0.1:3001，进入「统一记忆」页面
# 点击「召回审计」tab
# 截图验证：统计卡片、筛选栏、审计列表、展开行、hits 显示
```

### Step 3: 测试 feedback 功能

1. 展开一条有 hits 的审计记录
2. 点击某个 hit 的「👍 相关」按钮
3. 查询 PG 验证：
   ```sql
   SELECT id, hits FROM quant.memory_recall_audit 
   WHERE id = <刚才展开的记录ID>;
   -- 检查 hits JSONB 数组中对应 memory_id 的元素是否有：
   -- "feedback": "relevant", "feedback_by": "human", "feedback_at": "<时间戳>"
   ```

### Step 4: 测试 409 冲突处理

1. 用 `psql` 手动插入一条带 `feedback_by: 'human'` 的 hit
2. 前端尝试用 agent 标注（或反向测试）
3. 验证弹出错误提示：「无法覆盖已有的人工标注」

---

## 文件清单

**新增文件**:
- `web-frontend/src/views/Memory/RecallAudit.vue` (327 行)

**修改文件**:
- `web-frontend/src/services/api/memory.ts` (追加 RecallAuditItem/Hit/Stats 类型 + recallAuditApi 对象)
- `web-frontend/src/views/Memory/index.vue` (添加 el-tabs + RecallAudit 组件导入)

**依赖**:
- P1-T4 后端 API 部署（`feat/P1-T4` 分支需合并到 main 并重启 5001）

---

## 已知问题

无。

---

## 与计划的偏差

**无**。完全按照 `docs/superpowers/plans/2026-08-13-memory-recall-redesign.md` P1-T5 契约实现：
- ✅ API 层函数签名与契约逐字一致
- ✅ 页面包含所有要求的 UI 元素（统计卡片、筛选栏、列表、展开 hits、feedback 按钮）
- ✅ suppressed 行灰色样式
- ✅ feedback_by='human' 写入
- ✅ 无 mock 数据（等待真实后端）

---

**下一步**: 等待 P1-T4 合并到 main 并部署到生产 5001 端口后，执行上述验收步骤。
