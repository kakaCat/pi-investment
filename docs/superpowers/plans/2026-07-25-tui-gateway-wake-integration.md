# TUI 集成 Wake Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `npm run dev` 单进程同时运行 TUI + 旧 feishu bot + wake channel（gateway WakeAdapter，3002），共享 init 加幂等守卫消除重复初始化。

**Architecture:** 给 6 个共享 init 函数加模块级幂等守卫（重复调用跳过）；`api/index.ts` 在 `startFeishuBot()` 后以动态 import + try/catch 降级方式调用 `startGateway([new WakeAdapter()])`；退出路径挂 `gatewayHandle.shutdown()`。

**Tech Stack:** TypeScript / tsx / Jest（ESM，`jest.unstable_mockModule` 范式）

**Spec:** `docs/superpowers/specs/2026-07-25-tui-gateway-wake-integration-design.md`

**关键约定：**
- 仓库 monorepo，git 根在 `/Users/mac/Documents/ai/pi-investment`，git add 需带 `agent-ts/` 前缀
- 测试命令：`cd agent-ts && npm test -- <file>`
- **本任务期间工作区可能有其他会话的未提交改动——只 add 计划内文件，禁止 `git checkout <ref> -- .` 类操作**
- 当前分支由其他会话共享使用，直接在当前分支提交，勿切分支

---

### Task 1: 6 个共享 init 函数加幂等守卫

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/index.ts`（`initMemoryTools`）
- Modify: `agent-ts/src/services/intelligence/skill-router.ts`（`initSkillRouter`，约 119 行）
- Modify: `agent-ts/src/infrastructure/tools/skill-guard.ts`（`initSkillGuard`，约 22 行）
- Modify: `agent-ts/src/core/agent/system-prompt.ts`（`initSkillsBlock`，约 49 行）
- Modify: `agent-ts/src/infrastructure/tools/agent/plan-tool.ts`（`setPlanToolContext`，约 15 行）
- Modify: `agent-ts/src/infrastructure/plugins/index.ts`（`loadPlugins`，async，返回 PluginRegistry）
- Test: `agent-ts/src/api/gateway/init-idempotency.test.ts`

**守卫模式（所有同步函数统一）：** 模块级 `let initialized = false`，函数体第一行 `if (initialized) return; initialized = true;`。`loadPlugins` 用缓存 registry 模式（见 Step 3）。

- [ ] **Step 1: 写测试（先失败）**

创建 `agent-ts/src/api/gateway/init-idempotency.test.ts`：

```typescript
/**
 * 共享 init 函数幂等守卫测试
 * TUI 集成 wake 后，gateway bootstrap 会重复调用这些 init——重复调用必须无害。
 */
import { initSkillRouter } from "../../services/intelligence/skill-router.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import { initSkillsBlock } from "../../core/agent/system-prompt.js";
import { setPlanToolContext } from "../../infrastructure/tools/agent/plan-tool.js";
import { initMemoryTools } from "../../infrastructure/tools/index.js";
import { loadPlugins } from "../../infrastructure/plugins/index.js";
import { paths } from "../../config/config.js";

describe("共享 init 幂等守卫", () => {
  it("initMemoryTools 重复调用不报错", () => {
    expect(() => {
      initMemoryTools(paths.piDir);
      initMemoryTools(paths.piDir);
    }).not.toThrow();
  });

  it("initSkillRouter 重复调用不报错", () => {
    expect(() => {
      initSkillRouter([]);
      initSkillRouter([]);
    }).not.toThrow();
  });

  it("initSkillGuard 重复调用不报错", () => {
    expect(() => {
      initSkillGuard([]);
      initSkillGuard([]);
    }).not.toThrow();
  });

  it("initSkillsBlock 重复调用不报错", () => {
    expect(() => {
      initSkillsBlock([], []);
      initSkillsBlock([], []);
    }).not.toThrow();
  });

  it("setPlanToolContext 重复调用不报错", () => {
    expect(() => {
      setPlanToolContext([]);
      setPlanToolContext([]);
    }).not.toThrow();
  });

  it("loadPlugins 两次调用返回同一 registry（缓存，不重复加载）", async () => {
    const first = await loadPlugins(paths.pluginDirs);
    const second = await loadPlugins(paths.pluginDirs);
    expect(second).toBe(first); // 引用相等 = 缓存生效
  });
});
```

注意：`paths.pluginDirs` 若不存在，打开 `src/config/config.ts` 找 `start-gateway.ts` 实际使用的插件目录字段名（`loadPlugins(paths.pluginDirs)` 来自 start-gateway.ts 现有调用）并对齐。

- [ ] **Step 2: 运行测试确认 loadPlugins 用例失败**

```bash
cd agent-ts && npm test -- src/api/gateway/init-idempotency.test.ts
```

预期：前 5 个用例通过（这些函数重复调用本就无害），`loadPlugins 两次调用返回同一 registry` **失败**（当前每次重新加载，返回新对象）。

- [ ] **Step 3: 给 6 个函数加守卫**

`loadPlugins`（`src/infrastructure/plugins/index.ts`）改为缓存模式：

```typescript
let cachedRegistry: PluginRegistry | null = null;  // PluginRegistry 用该文件现有类型名

export async function loadPlugins(dirs: string[]): Promise<PluginRegistry> {
  if (cachedRegistry) return cachedRegistry;
  cachedRegistry = await doLoadPlugins(dirs);  // 原函数体重命名/内联为 doLoadPlugins
  return cachedRegistry;
}
```

其余 5 个函数在各文件内加模块级标志与首行守卫，示例（`initSkillGuard`）：

```typescript
let skillGuardInitialized = false;

export function initSkillGuard(skills: Skill[]): void {
  if (skillGuardInitialized) return;
  skillGuardInitialized = true;
  allowedToolsBySkill.clear();
  // ... 原函数体其余部分不变
}
```

各函数守卫变量名：`memoryToolsInitialized`（initMemoryTools）、`skillRouterInitialized`（initSkillRouter）、`skillGuardInitialized`（initSkillGuard）、`skillsBlockInitialized`（initSkillsBlock）、`planToolContextInitialized`（setPlanToolContext）。

注意：守卫必须放在函数体**第一行**，原逻辑一行不改。若某函数已存在类似守卫则跳过该文件。

- [ ] **Step 4: 运行测试确认全过**

```bash
cd agent-ts && npm test -- src/api/gateway/init-idempotency.test.ts
```

预期：6 passed

- [ ] **Step 5: tsc + 相关回归**

```bash
cd agent-ts && npx tsc -p tsconfig.build.json --noEmit
npm test -- src/api/gateway/ src/infrastructure/tools/agent/plan-tool.test.ts 2>&1 | tail -5
```

预期：tsc 无 error；gateway 目录既有测试（wake-adapter、gateway、session-* 等）全过

- [ ] **Step 6: Commit**

```bash
git add agent-ts/src/infrastructure/tools/index.ts agent-ts/src/services/intelligence/skill-router.ts agent-ts/src/infrastructure/tools/skill-guard.ts agent-ts/src/core/agent/system-prompt.ts agent-ts/src/infrastructure/tools/agent/plan-tool.ts agent-ts/src/infrastructure/plugins/index.ts agent-ts/src/api/gateway/init-idempotency.test.ts
git commit -m "feat: 共享 init 函数幂等守卫（TUI 集成 gateway 前置）"
```

---

### Task 2: TUI 集成 startGateway([WakeAdapter]) + 退出钩子

**Files:**
- Modify: `agent-ts/src/api/index.ts`（约 307-313 行 feishu 启动块之后插入 gateway 启动；约 376 行 shutdown 处加钩子）

- [ ] **Step 1: 读取集成点上下文**

```bash
sed -n 300,330p agent-ts/src/api/index.ts
sed -n 365,385p agent-ts/src/api/index.ts
```

确认 `feishuBot = await startFeishuBot();` 与 `if (feishuBot) feishuBot.shutdown();` 的实际行号与上下文（行号可能因其他会话改动漂移，以实际内容为准）。

- [ ] **Step 2: 插入 gateway 启动代码**

在 `feishuBot = await startFeishuBot();` 及其后的 `if (feishuBot) {...}` 块之后插入：

```typescript
    // Wake channel（gateway WakeAdapter）：与 TUI/feishu 同进程提供 /wake 接收
    // 失败仅降级警告，不影响 TUI 与 feishu
    let gatewayHandle: import("./gateway/start-gateway.js").GatewayHandle | null = null;
    try {
      const { startGateway } = await import("./gateway/start-gateway.js");
      const { WakeAdapter } = await import("./gateway/adapters/wake-adapter.js");
      gatewayHandle = await startGateway([new WakeAdapter()]);
      console.log("🔔 Wake channel 已集成启动（127.0.0.1:3002）");
    } catch (err) {
      console.warn("⚠️ Wake channel 启动失败（降级，不影响 TUI/feishu）:", err instanceof Error ? err.message : err);
    }
```

- [ ] **Step 3: 退出路径加 shutdown 钩子**

在 `if (feishuBot) feishuBot.shutdown();` 紧邻其后加：

```typescript
      if (gatewayHandle) await gatewayHandle.shutdown();
```

注意：`gatewayHandle` 变量声明必须位于 shutdown 代码的同一作用域内可见——若启动块与 shutdown 块处于不同函数/作用域，把 `let gatewayHandle` 提升到与 `let feishuBot`（约 307 行）同级，启动块内只做赋值。

- [ ] **Step 4: tsc 检查**

```bash
cd agent-ts && npx tsc -p tsconfig.build.json --noEmit
```

预期：无 error（`GatewayHandle` 类型已从 start-gateway.ts export，spec 设计中有 `export interface GatewayHandle`）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/index.ts
git commit -m "feat: TUI 进程集成 wake channel（startGateway + WakeAdapter，降级启动 + 退出钩子）"
```

---

### Task 3: 集成冒烟验证

**Files:** 无新增（手工验证）

- [ ] **Step 1: 确认 3002 空闲（先停掉独立 wake 进程，避免端口占用降级路径干扰验证）**

```bash
lsof -nP -iTCP:3002 -sTCP:LISTEN -t | xargs kill 2>/dev/null; sleep 1
lsof -nP -iTCP:3002 -sTCP:LISTEN || echo "3002 空闲"
```

- [ ] **Step 2: 后台启动 TUI 并等待 wake 就绪**

```bash
cd agent-ts && npx tsx src/index.ts > /tmp/tui-integrated-smoke.log 2>&1 &
```

等待（until 循环，最多 90s）：
- `/tmp/tui-integrated-smoke.log` 出现 `Wake channel 已集成启动` 或 `Wake channel 启动: http://127.0.0.1:3002`
- `curl -s http://127.0.0.1:3002/wake/health` 返回 `{"status":"ok",...}`

预期：两者都成立。若 TUI 在无 TTY 环境下启动失败（pi-tui 报错），记录现象，改为请用户在真实终端跑 `npm run dev` 人工验证（这是可接受的备选——TUI 本来就要求 TTY）。

- [ ] **Step 3: 发测试事件验证处理链路**

```bash
curl -s -m 120 -X POST http://127.0.0.1:3002/wake -H 'Content-Type: application/json' \
  -d '{"event":"agent_reminder","data":{"message":"TUI 集成冒烟测试：直接回复 ok 即可，不要调用任何工具"},"timestamp":"2026-07-25T15:00:00"}'
```

预期：`{"success":true,"event":"agent_reminder",...}`

- [ ] **Step 4: 验证退出钩子**

杀掉 TUI 进程（SIGTERM）：`kill <pid>`，等待 3s 后 `lsof -nP -iTCP:3002 -sTCP:LISTEN` 应为空（gatewayHandle.shutdown 释放了监听）。

- [ ] **Step 5: 更新 spec 状态 + Commit**

把 `docs/superpowers/specs/2026-07-25-tui-gateway-wake-integration-design.md` 状态改为 `**状态**: 已实现（2026-07-25）`：

```bash
git add docs/superpowers/specs/2026-07-25-tui-gateway-wake-integration-design.md
git commit -m "docs: TUI 集成 wake spec 状态更新为已实现"
```

---

## Self-Review 记录

- **Spec 覆盖**：6 个幂等守卫（T1）✓ / 动态 import + 降级启动（T2 Step 2）✓ / 退出钩子（T2 Step 3）✓ / 幂等单测（T1 Step 1）✓ / 集成验证含健康检查、测试事件、退出释放（T3）✓ / 不动旧 feishu、保留 npm run wake（无任务涉及，符合 YAGNI）✓
- **类型一致性**：`GatewayHandle` 在 start-gateway.ts 已 export（spec 与 T2 引用一致）；`paths.pluginDirs` 在 T1 Step 1 给了对齐指引
- **已知风险**：T3 的 TUI 无 TTY 启动可能失败，已给用户终端人工验证的备选路径
