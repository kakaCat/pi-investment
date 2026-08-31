# M6-1 决策前检索（R-008）集成验证报告

- 日期：2026-08-31
- 验证人：investor（w-8366e526）
- 状态：✅ 集成已存在并验证通过（含 3 处字段契约 bug 修复）
- 关联：RFC 005 M6 学习飞轮 / genome rules R-008

## 结论摘要

用户质疑"memory_search 集成是否真的存在于 portfolio_trade 流程"。**验证结果：集成确实存在且真实工作**，早前审计文档（code-completion-audit-20260831.md）标注 M6-1=0% 是过时结论。同时验证过程中发现并修复了 memory 插件 3 处字段契约 bug。

## 一、R-008 集成链路验证（portfolio_trade 内部）

### 集成存在性（代码证据）

1. `packages/trading/src/tools/PortfolioTradeTool/PortfolioTradeTool.ts`
   - 构造函数接收 `osMemory`（第 181 行调用 `this.osMemory.search(...)`）
   - reason 解析标记"已检索"；检索失败降级放行（soft enforce）
   - 返回 `r008_check` 字段（约第 204/212/249/255 行）
2. `packages/trading/src/index.ts`
   - `OsMemoryStore` 内联类：`search()` 方法（第 61-65 行）→ `searchMemory()` → Agent OS `GET /api/v1/memory/search`
   - 第 126 行 `new OsMemoryStore({baseURL:'http://localhost:8080', agentId:'agent-dh'})`；第 135 行注册 `createPortfolioTradeTool(qv2, osMemory, ctx)`
3. `packages/memory` 插件 `memory_search` 工具走同一 Agent OS 存储（`MemoryClient.search`）

### 运行时验证（tsx 直接加载源码实测）

```
osMemory.search({query:'600519', namespace:'experience', top_k:3})
→ R-008 search memories: 3
  - [auto-track portfolio_trade fail (g16)] kind=experience status=testing conf=0.3
  - ...（共 3 条）
```

与 PortfolioTradeTool 内部调用签名一致，检索到 experience 数据。

### Agent OS 依赖

- Agent OS（:8080）运行中（PID 9159），memory 接口正常
- 已存有 600519 经验数据（learning auto-track + experience_write）
- 检索失败路径降级放行（不阻断交易），符合 R-008 "soft enforce" 语义

## 二、发现的 3 处字段契约 bug（已修复）

| 文件 | Bug | 修复 |
|---|---|---|
| `MemorySearchTool.ts` | 读 `res.items`，后端返回 `{memories: [...]}` → memory_search 恒返回 0 条 | `res?.memories ?? res?.items ?? []` |
| `MemoryWriteTool.ts` | 读 `res?.id`，后端 write 返回 `{memory: {id}}` → memory_id 恒为空串 | `res?.memory?.id ?? res?.id` |
| `ExperienceWriteTool.ts` | 同上 → experience_id 恒为空串 | `res?.memory?.id ?? res?.id` |

### 修复验证（tsx 实测）

- `memory_search`：修复前 0 条 → 修复后 q=600519交易经验 返回 3 条
- `memory_write`：返回真实 UUID `9ce73fc2-...`
- `experience_write`：返回真实 UUID `a9c507b5-...`

注：`OsMemoryStore.searchMemory`（portfolio_trade 用的链）原本就兼容 `res?.memories ?? res?.items`，无此 bug；memory 插件的 3 个工具是唯一受影响点。

## 三、⚠️ 阻塞项：evolver 插件 schema 违规（非本任务文件）

重启验证时发现 DSH 启动失败，根因**不是 memory 修复**，而是工作区中其他会话改动的 `packages/evolver/src/tools/PromptEvolverTool/PromptEvolverTool.ts` 新增 `toDSHToolDefinition()` 覆盖违反 Schema 铁律：

```typescript
parameters: {
  suggestions: { type: 'array', ..., items: { type: 'object', additionalProperties: true } },
  ...
}
// 缺 { type:'object', properties: {...}, additionalProperties: true } 包装
// → dsh-tools rc7 UNSUPPORTED_SCHEMA → 插件树加载失败 → DSH 启动即崩
```

- 失败日志：`~/.dsh/profiles/investment/state/restart-1788178870776.log`
- 失败分支：`agent-self/20260831-202110`，restart-result.json status=dead
- 该文件修改时间 20:30（重启失败之后），判定为并行会话在主工作区直接改动（未按 CLAUDE.md worktree 隔离规则）
- **影响**：memory 修复代码已就位但需重启才生效；evolver 修复前任何重启都会失败

### 建议处置

1. 让 evolver 改动方修正 `toDSHToolDefinition` 的 parameters 结构（补 `type:'object'`/`properties`/`additionalProperties`），或
2. 回退该覆盖（恢复 BaseTool 默认实现），或
3. 由本窗口协助修复（需用户确认，避免与并行会话冲突）

修复后重启 DSH，memory_search/memory_write/experience_write 3 处修复即生效。

## 四、M6-1 完成度更新

- 早前审计：M6-1 = 0%（"未集成到 portfolio_trade"）→ **过时，错误**
- 更新后：**M6-1 = 100%**（R-008 集成已存在、验证通过；附带修复 3 处 memory 插件字段契约 bug）
- M6 整体：60% → 65%（M6-2 归因待 M5-1 滑点数据、M6-4 进化待 M3-2 回测矩阵，均依赖他模块）

## 附：验证脚本痕迹

验证用临时脚本已删除（/tmp 与 agent-dh 根目录，tsx 模式直接加载源码，未改动任何运行文件）。
