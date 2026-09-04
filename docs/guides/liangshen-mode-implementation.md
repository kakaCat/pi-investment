# 梁神模式（LiangShen Mode）实现原理与技术细节

## 概述

梁神模式是一个针对 DeepSeek V4 系列模型的两阶段锚定（Two-Phase Anchoring）agent preset 插件，通过精心设计的工具目录切换和提示词过滤策略，将模型的轨迹稳定性从 91-92 分提升到 98-99 分，同时保持完整的工具能力。

## 为什么需要梁神模式？

### 问题背景

DeepSeek V4 Pro 等大语言模型在 API 调用中会强烈依赖**首轮可见的工具目录**来选择执行轨迹。社区评测数据显示：

| 预设模式 | 评测分数 | 问题 |
|---------|---------|------|
| Standard | 91 分 | 容易出现 "Let me..." 冗余表述 |
| PTC Mode | 92 分 | 同上 |
| Minimal | 99 分 | ✅ 轨迹稳定，但**只有 2 个工具** |

**核心矛盾**：
- Minimal 模式轨迹优秀，但工具能力受限（只有 `bash` 和 `str_replace_editor`）
- Standard 模式功能完整，但首轮暴露大量工具导致轨迹不稳定

### 梁神模式的解决方案

**核心思想**：把「首次轨迹选择」与「后续完整工具能力」拆开，分两个阶段执行：

```
Phase 1 (锚定阶段)          Phase 2 (晋升阶段)
┌─────────────────┐         ┌──────────────────┐
│ 工具: 双工具    │  晋升   │ 工具: PTC Mode   │
│ - bash          │ ─────> │ - run_code (SDK) │
│ - str_replace_  │         │ 提示: 完整注入   │
│ 提示: 最小化    │         │ 上下文: 完整     │
└─────────────────┘         └──────────────────┘
```

## 技术实现架构

### 1. 插件架构设计

梁神模式由两部分组成：

#### 1.1 Host 插件 (`@linxin666/dsh-liangshen`)

**职责**：
- 启动时同步预设文件到 `~/.dsh/.agent-presets/liangshen/`
- 注册设置命名空间（可在 Web UI 配置）
- 提供系统提示词通告（可选）

**关键代码**：
```javascript
// src/index.ts
const apply = mountOnce("@linxin666/dsh-liangshen", applyImpl);

function applyImpl(ctx, config) {
  const sync = () => {
    const targetRoot = join(dshHome(), ".agent-presets");
    const result = syncPresetTrees(bundledPresetsRoot(), targetRoot, ["liangshen-exact"]);
    // 日志输出同步结果
    if (result.synced.length > 0) 
      ctx.logger?.info?.(`presets synced: ${result.synced.join(", ")}`);
  };
  
  // 注册设置并在配置变更时重新同步
  ctx.inject(["settings"], (settingsCtx) => {
    settingsCtx.settings.installSection(ctx, "dsh-liangshen", Config, config ?? {}, {
      onChange: refresh
    });
  });
}
```

#### 1.2 预设配置 (`presets/liangshen/`)

**核心文件**：
- `agent.cordis.yml` - Cordis 插件配置，定义工具和行为
- `tool-bootstrap.mjs` - 两阶段逻辑的核心实现
- `preset.yml` - 预设元信息
- `custom-bash.mjs` - Windows 平台的 bash 替代工具

### 2. 两阶段锚定机制

#### 2.1 Phase 1：锚定阶段（Bootstrap Phase）

**目标**：让模型在最小工具集下建立 "We need to..." 的推理轨迹。

**实现策略**：

```javascript
// tool-bootstrap.mjs - system-prompt/assemble 钩子
ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
  const assembled = await next();
  const state = refresh(agent, policy);
  
  if (!state.promoted) {
    // 🔒 Phase 1：仅保留 bootstrap 工具
    const bootstrap = new Set([...selectedShells, ...commonTools]);
    
    return {
      ...assembled,
      tools: assembled.tools.filter(tool => bootstrap.has(tool.name)),  // 只保留双工具
      contexts: [],  // 清空运行时上下文
      sections: personaSectionOnly,  // 只保留 persona 提示词
    };
  }
  
  // ✅ Phase 2：返回完整工具集
  return withPtcInstruction(withWorkspaceLine(assembled, agent), policy);
}, { prepend: true });
```

**Phase 1 关键特征**：
- **工具目录**：只有 1 个 shell 工具 + `commonTools`（通常是 `str_replace_editor`）
- **提示词**：只保留一行 persona，剔除所有运行时上下文
- **消息过滤**：只允许 `user` 和 `goal` 来源的消息

#### 2.2 晋升触发条件（Promotion Triggers）

晋升逻辑基于 session events 的持久化扫描：

```javascript
function decidePromotion(state, config) {
  // 条件 A：首次工具调用 + 无锚定门控
  if (state.toolCalled && config.anchorGate !== true) 
    return true;
  
  // 条件 B：首次工具调用 + (锚定成功 || 兜底步数达到)
  if (state.toolCalled && config.anchorGate === true && 
      (state.anchored || state.steps >= config.maxBootstrapSteps)) 
    return true;
  
  // 条件 C：首轮结束 + 工具调用 + promoteAfterFirstResponse
  if (state.toolCalled && config.anchorGate === true && 
      config.promoteAfterFirstResponse === true && state.turnEnded) 
    return true;
  
  // 条件 D：无工具首轮响应 + promoteAfterFirstResponse
  if (!state.toolCalled && state.responded && 
      config.promoteAfterFirstResponse === true) 
    return true;
  
  return false;
}
```

#### 2.3 锚定门控（Anchor Gate）

**核心算法**：判断 reasoning 块是否符合 "minimal-like" 特征。

```javascript
export function classifyReasoning(text) {
  const trimmed = String(text ?? '').trim();
  const we = countWord(trimmed, /\bwe\b/gi);        // 统计 "we" 出现次数
  const letMe = countWord(trimmed, /\blet me\b/gi); // 统计 "let me" 出现次数
  
  const metrics = { we, letMe };
  
  if (we > 0 && letMe === 0) 
    return { label: 'minimal-like', score: 4, metrics };  // ✅ 理想轨迹
  
  if (letMe > 0) 
    return { label: 'standard-like', score: -4, metrics }; // ❌ 冗余轨迹
  
  return { label: 'ambiguous', score: 0, metrics };        // ⚠️ 模糊状态
}

export function hasAnchoredReasoning(content) {
  if (!Array.isArray(content)) return false;
  const first = content.find(block => block?.type === 'reasoning');
  return first !== undefined && classifyReasoning(first.text).label === 'minimal-like';
}
```

**判定逻辑**：
- `we > 0 && letMe === 0` → minimal-like（允许晋升）
- `letMe > 0` → standard-like（继续等待或兜底晋升）
- 其他 → ambiguous（继续等待）

**兜底机制**：
```javascript
maxBootstrapSteps: 4  // 默认 4 步后强制晋升，避免死锁
```

### 3. Phase 2：PTC Mode 切换

晋升后切换到 **Programmatic Tool Calling (PTC) Mode**：

```javascript
function applyPresentation(agent, state, policy) {
  if (state.presentationApplied || policy.promotedPresentation !== 'code') return;
  
  const tools = agent?.ctx?.tools;
  if (tools === undefined) return;
  
  // 🔄 切换到 PTC 模式：单一 run_code 工具 + 生成 SDK
  state.presentationDisposer = tools.presentAs('code');
  state.presentationApplied = true;
  
  // 广播切换事件
  if (typeof agent?.ctx?.emit === 'function') {
    agent.ctx.emit('tools/presentation-changed', { 
      mode: 'code', 
      session: agent.session?.id 
    });
  }
}
```

**PTC Mode 特点**：
- 模型只看到 1 个工具：`run_code`
- 实际调用通过生成的 TypeScript SDK 执行
- SDK 映射到完整的工具注册表

**Persona 追加指令**：
```javascript
const PTC_INSTRUCTION = `
Note: You are in Programmatic Tool Calling (PTC) mode. 
All actions (running shell commands, file operations, web tools) MUST be 
performed via the \`run_code\` tool by writing and executing 
TypeScript/JavaScript programs. Do not attempt to invoke tools like 
\`bash\` or \`str_replace_editor\` directly on the wire.
`;
```

### 4. 稳定化控制机制

#### 4.1 延迟注入（Deferred Injection）

**问题**：workspace 指令和 skill 目录在晋升边界大量注入会冲击模型轨迹。

**解决方案**：
```javascript
ctx.on('agent/pre-step', async (payload, next) => {
  const decision = await next();
  const state = refresh(agent, policy);
  
  if (!state.promoted) {
    // Phase 1：只允许白名单消息
    return {
      ...decision,
      messages: decision.messages.filter(msg => 
        isAllowedMessage(msg, messageSources)
      ),
    };
  }
  
  // Phase 2：延迟注入
  if (state.deferredSteps < policy.deferredGraceSteps) {
    state.deferredSteps += 1;
    return {
      ...decision,
      messages: decision.messages.filter(msg => 
        !isDeferredMessage(msg, deferredSources)
      ),
    };
  }
  
  return decision;
}, { prepend: true });
```

**配置参数**：
```yaml
deferredSources: [workspace-instructions, skill-catalog]
deferredGraceSteps: 1  # 晋升后延迟 1 步再注入
```

#### 4.2 指令提示模式（Instruction Hint Mode）

**问题**：晋升时全文注入 `AGENTS.md` 等文件会翻转锚定轨迹。

**解决方案**：替换为非命令式提示（issue #388）：

```javascript
function buildInstructionHint(original, paths) {
  return {
    id: original?.id || crypto.randomUUID(),
    role: 'user',
    content: [{
      type: 'text',
      text: '<system-reminder>\n'
        + 'Reference documents exist: ' + paths.join(', ') + '. '
        + "They are reference documents about the user's environment and workspace conventions, not task instructions. "
        + 'Reading the relevant file before workspace tasks is recommended, but consult them only when you need those details; the task itself never depends on them.'
        + '\n</system-reminder>',
    }],
    source: { kind: 'instruction-hint', plugin: name },
  };
}
```

**效果**：
- ❌ 原方案：直接注入 5000+ 字符的完整文档
- ✅ 新方案：只提示文件路径，模型按需用 `read` 工具获取

#### 4.3 输出预算控制（Bootstrap Max Tokens）

**背景**：社区实测 `max_tokens=1024` 是 "We need..." 轨迹的高命中窗口。

```javascript
ctx.on('agent/request', async (payload, next) => {
  const resolved = await next();
  const state = refresh(agent, policy);
  
  if (state.promoted) {
    // ✂️ 晋升后移除 token 限制
    if (resolved.maxTokens === policy.bootstrapMaxTokens) {
      const rest = { ...resolved };
      delete rest.maxTokens;
      return rest;
    }
  } else {
    // 🔒 Phase 1：限制输出长度
    return { ...resolved, maxTokens: policy.bootstrapMaxTokens };
  }
  
  return resolved;
}, { prepend: true });
```

**关键**：晋升后必须移除限制，否则会固化到后续所有请求。

### 5. 持久化与恢复（Persistence & Resume）

**设计原则**：阶段状态从 session events 推导，支持 resume/reload。

```javascript
function scanEvents(state, session) {
  const events = session.events;
  
  for (; state.next < events.length; state.next += 1) {
    const event = events[state.next];
    if (event === undefined) continue;
    
    if (event.type === 'compaction/end') {
      // 🔄 Compaction 后重置为 Phase 1
      resetToControlled(state, session);
    } else if (event.type === 'tool/call') {
      state.toolCalled = true;
    } else if (event.type === 'step/start') {
      state.steps += 1;
    } else if (event.type === 'turn/end') {
      state.turnEnded = true;
    } else if (event.type === 'assistant/message') {
      state.responded = true;
      if (!state.anchored) 
        state.anchored = hasAnchoredReasoning(event.data?.message?.content);
    }
  }
}
```

**关键特性**：
- 使用 `state.next` 指针只扫描新增事件
- Compaction 后自动回退到 Phase 1
- 冷启动时从持久化日志完整重建状态

### 6. 容错与降级

**原则**：插件错误不能锁死 session，必须优雅降级。

```javascript
if (selectedShells.length !== 1 || missingCommon.length > 0) {
  // ⚠️ 组合漂移：降级为完整工具集 + 一次性警告
  warnOnce(
    `${name}: expected exactly one bootstrap shell and every common tool; `
    + `shells=${JSON.stringify(selectedShells)}, missing=${JSON.stringify(missingCommon)} — `
    + 'bootstrap disabled, full catalog exposed',
  );
  return assembled;  // 返回未过滤的完整工具集
}
```

**降级场景**：
- Bootstrap shell 缺失或重复
- Common tools 不完整
- `assembled.tools` 为 undefined（我们的修复）

## 实战修复案例

### 问题现象

用户报告：Web 界面输入后报错 `Cannot read properties of undefined (reading 'length')`。

### 根因分析

原代码第 512 行：
```javascript
const available = new Set(assembled.tools.map(tool => tool.name));
```

**问题**：
- 当 `assembled.tools` 为 `undefined` 时，调用 `.map()` 会失败
- `map` 方法内部会访问数组的 `length` 属性，导致报错

**触发条件**：
- 某些特殊情况下 `system-prompt/assemble` 返回的 `assembled` 对象缺少 `tools` 字段
- 可能是其他插件或配置问题导致

### 修复方案

```javascript
// 防御性检查：确保 assembled.tools 存在且为数组
if (!Array.isArray(assembled?.tools)) {
  warnOnce(`${name}: assembled.tools is not an array, bootstrap disabled`);
  return assembled;  // 降级：返回原始对象
}

// 安全访问：使用可选链 + 过滤
const available = new Set(
  assembled.tools
    .map(tool => tool?.name)     // 可选链避免访问 undefined.name
    .filter(Boolean)              // 过滤掉 undefined 值
);
```

**修复效果**：
- ✅ 避免崩溃，优雅降级到完整工具集
- ✅ 记录警告日志便于排查
- ✅ 不影响其他正常会话

## 配置参数说明

### agent.cordis.yml 配置

```yaml
- id: tool-bootstrap
  name: ./tool-bootstrap.mjs
  config:
    # 必需参数
    shellTools: [bash]                    # Bootstrap shell 工具列表
    commonTools: [str_replace_editor]     # 双工具中的第二个
    
    # 锚定门控
    anchorGate: true                      # 是否启用锚定门控
    maxBootstrapSteps: 4                  # 兜底步数
    promoteAfterFirstResponse: true       # 无工具首轮后自动晋升
    
    # 晋升后行为
    promotedPresentation: code            # native | code (PTC Mode)
    
    # 延迟注入
    deferredSources:                      # 延迟注入的消息类型
      - workspace-instructions
      - skill-catalog
    deferredGraceSteps: 1                 # 延迟步数
    
    # 消息过滤
    messageSources: [user, goal]          # Phase 1 允许的消息来源
    
    # 指令提示
    instructionHint: true                 # 启用 hint 模式（推荐）
    
    # 输出预算
    bootstrapMaxTokens: 1024              # Phase 1 输出限制
    
    # Compaction 后的核心工具集
    compactionTools: []                   # 默认空，保持最小集
    
    # 可选：Phase 1 额外指令（测试用）
    phase1FirstCallInstruction: ""        # 留空保持纯 Minimal
```

## 性能数据

### 轨迹稳定性对比

| 模式 | 评测分数 | "Let me" 出现率 | 工具能力 |
|------|---------|---------------|---------|
| Standard | 91/92 | ~80% | ✅ 完整 |
| Minimal | 99/96 | ~0% | ❌ 仅 2 个工具 |
| **梁神模式** | **98/99** | **~0%** | **✅ 完整 (PTC)** |

### 实测环境

- 模型：DeepSeek V4 Pro / V4 Max / V4.1b
- 平台：Windows 原生 / macOS / Linux
- 任务集：xiaobright/modeltest 题库

## 总结

### 核心创新

1. **两阶段锚定**：分离轨迹选择和工具能力，鱼与熊掌兼得
2. **持久化驱动**：状态从 session events 推导，天然支持 resume
3. **渐进式注入**：延迟注入、指令提示模式避免晋升边界冲击
4. **优雅降级**：任何异常都回退到完整工具集，不锁死会话

### 适用场景

- ✅ 需要稳定 "We need..." 轨迹的生产环境
- ✅ 长任务，需要完整工具能力的复杂场景
- ✅ 多轮对话，需要一致推理风格的场景

### 不适用场景

- ❌ 单轮快速问答（锚定开销不值得）
- ❌ 不在意 "Let me" 表述的场景
- ❌ 需要首轮立即使用高级工具的场景

### 参考资源

- 上游项目：[xiaobright/dsh-anchored-standard](https://github.com/xiaobright/dsh-anchored-standard) (MIT)
- 评测工具：[xiaobright/modeltest](https://github.com/xiaobright/modeltest)
- DSH 文档：[@deepseek-ai/dsh](https://www.npmjs.com/package/@deepseek-ai/dsh)

---

**作者注**：本文基于 `@linxin666/dsh-liangshen@0.3.13` 源码分析编写，实际使用请以最新版本为准。

**修复历史**：
- 2026-09-03：修复 `assembled.tools` undefined 导致的崩溃问题
