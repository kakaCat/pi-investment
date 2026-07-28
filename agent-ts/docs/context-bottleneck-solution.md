# LLM 上下文瓶颈解决方案 — 实施记录

> 日期: 2026-07-25 | 状态: Phase 1 完成 + Phase 2 框架就绪

## 诊断结果

| 组件 | 消耗(tokens) | 占比 |
|------|:--:|:--:|
| SOUL.md (bootstrap) | ~4,100 | 12.8% |
| TOOLS.md (bootstrap, 已优化前) | ~1,980 | 6.2% |
| 其他 bootstrap 文件 | ~6,500 | 20.3% |
| System prompt builder 输出 | ~3,000 | 9.4% |
| API tools 参数 (75个工具定义) | ~10,700 | 33.4% |
| Skills + Memory + Runtime | ~5,720 | 17.9% |
| **总计** | **~32,000** | **50% of 64K** |

> 注意：SOUL.md 的 14K chars 是被 BootstrapLoader 的 MAX_FILE_CHARS=20K 限制截断后的结果。原始 SOUL.md 更大。

## 已实施优化 (Phase 1)

### 1. TOOLS.md 精简
- **Before**: 6,923 chars (~1,980 tokens) — 大量与 SOUL.md 重叠的内容
- **After**: 178 chars (~50 tokens) — 仅保留工具使用核心规则
- **节省**: ~1,930 tokens

### 2. System Prompt Builder 优化
- 工具列表从完整描述压缩为短描述（每工具 <60 字符）
- 工具使用细则增加 2000 字符上限
- **节省**: ~570 tokens

### 3. 动态工具分组系统 (框架就绪)
- 新增 `src/infrastructure/tools/tool-groups.ts` — 75工具 → Core(~30) + 9个On-Demand组
- 新增 `src/infrastructure/tools/agent/load-tools-tool.ts` — LLM 可调用的元工具
- 已接入 agent-loop（`initToolGroups`）

### Phase 1 总计节省: ~2,500 tokens (3.9% of 64K)

## 待实施 (Phase 2 — 需要 SDK 级改动)

### 动态工具加载 (预计节省 ~7,000 tokens)
核心思路：使用 SDK 的 `initialActiveToolNames` 只在 session 启动时激活 Core 工具（~30个），LLM 通过 `load_tools` 元工具按需激活其他组。

**阻塞原因**: SDK 的 `setActiveToolsByName()` 会覆盖自定义 8 层 system prompt。需要：
- 方案 A: 修改 agent-loop，在工具切换后重新注入自定义 prompt
- 方案 B: 等待 SDK 支持 prompt-preserving tool switching
- 方案 C: 升级至支持更大窗口的模型（Kimi K3 有 256K 窗口）

### 模型升级 (终极方案)
当前 DeepSeek-chat: 64K 窗口 → 升级至 Kimi K3: 256K 窗口，瓶颈自然解除。

```bash
# 只需修改环境变量
LLM_PROVIDER=kimi
KIMI_API_KEY=sk-...
```

## 当前上下文预算 (优化后)

| 组件 | tokens | 
|------|:--:|
| Bootstrap (含 SOUL.md) | ~10,500 |
| System prompt builder | ~2,430 |
| API tools 参数 (75个) | ~10,700 |
| Skills + Memory + Runtime | ~5,720 |
| **总计** | **~29,350** |
| 可用对话空间 | ~34,650 (54%) |

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `.pi-invest/bootstrap/TOOLS.md` | 精简 — 6,923 → 178 chars |
| `src/infrastructure/tools/tool-groups.ts` | **新增** — 工具分组系统 |
| `src/infrastructure/tools/agent/load-tools-tool.ts` | **新增** — 动态加载元工具 |
| `src/infrastructure/tools/index.ts` | 导入 tool-groups + load_tools |
| `src/core/agent/agent-loop.ts` | 导入 CORE_TOOLS + initToolGroups |
| `src/services/intelligence/system-prompt-builder.ts` | 工具列表压缩 |
