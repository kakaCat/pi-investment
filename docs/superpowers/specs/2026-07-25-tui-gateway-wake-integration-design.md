# TUI 集成 Wake Channel（Phase 2 单进程多通道）设计

**日期**: 2026-07-25
**状态**: 已批准（设计评审通过）
**范围**: agent-ts 单项目。quantsys-v2 零改动（v2 只认 `AGENT_API_URL=http://127.0.0.1:3002`，不关心哪个进程在监听）

## 背景

当前 agent-ts 三个进程各司其职：

| 进程 | 入口 | 内容 |
|---|---|---|
| `npm run dev` | `src/index.ts` | TUI 交互 + **旧版 feishu bot**（`api/index.ts:313` `startFeishuBot()`，退出时 shutdown） |
| `npm run feishu` | `src/api/feishu.ts`（npm script 仍指旧实现） | 旧版 feishu bot 独立进程 |
| `npm run wake` | `src/api/start-wake-channel.ts` | gateway 版 wake channel（`startGateway([new WakeAdapter()])`，监听 3002） |

gateway（`src/api/gateway/`）按 Phase 2 设计支持单进程多 adapter，但 TUI 入口未接入。目标：`npm run dev` 一个进程同时提供 TUI + feishu（旧实现，不动）+ wake channel。

**已确认决策**：
1. 范围：**只加 wake**。旧 feishu.ts 保持不动；gateway 版 feishu 迁移由另一工作线负责
2. 重复初始化处理：**给共享 init 函数加幂等守卫**（不用 skipSharedInit 选项）
3. 可用性取舍：用户接受"TUI 不开 = wake 停止"（v2 侧 notify 失败会落库 `notified=false` 审计）

## 架构

```
npm run dev (src/index.ts)
  └─ api/index.ts 启动序列
       ├─ TUI 主体（现有，不动）
       ├─ 旧 feishu bot（现有，不动）
       └─ startGateway([new WakeAdapter()])        ← 新增
            ├─ 共享 init（幂等守卫 → 已初始化的自动跳过）
            ├─ AgentGateway + wake 独立会话
            └─ WakeAdapter 监听 127.0.0.1:3002
```

## 组件

### 1. 幂等守卫

以下 6 个初始化函数加模块级 `let initialized = false` 守卫，重复调用直接跳过；不改函数签名：

| 函数 | 模块 | 重复调用风险（无守卫时） |
|---|---|---|
| `initMemoryTools` | `infrastructure/tools/index.ts` | 记忆工具重复初始化 |
| `initSkillRouter` | `services/intelligence/skill-router.ts` | 重建路由状态（无害但浪费） |
| `initSkillGuard` | `infrastructure/tools/skill-guard.ts` | 守卫重复挂载 |
| `initSkillsBlock` | `core/agent/system-prompt.ts` | 覆盖 skills 提示块 |
| `setPlanToolContext` | `infrastructure/tools/agent/plan-tool.ts` | 上下文重复设置 |
| `loadPlugins` | `infrastructure/plugins/index.ts` | 插件工具重复注册；守卫后返回缓存的 registry |

### 2. TUI 集成点

`src/api/index.ts` 在 `startFeishuBot()`（约 313 行）之后：

```typescript
let gatewayHandle: GatewayHandle | null = null;
try {
  const { startGateway } = await import("./gateway/start-gateway.js");
  const { WakeAdapter } = await import("./gateway/adapters/wake-adapter.js");
  gatewayHandle = await startGateway([new WakeAdapter()]);
} catch (err) {
  console.warn("⚠️ Wake channel 启动失败（降级，不影响 TUI/feishu）:", err);
}
```

- 动态 import：避免 gateway 依赖拖慢/阻塞 TUI 主启动路径
- 失败仅警告降级，TUI 和 feishu 不受影响
- 3002 被占（有独立 wake 进程在跑）时 listen 报错走同一降级路径，不起重复监听

### 3. 生命周期

现有退出路径（`api/index.ts` 约 376 行 `feishuBot.shutdown()` 同一处）增加：

```typescript
if (gatewayHandle) await gatewayHandle.shutdown();
```

restart_agent 重启时：旧进程关闭 3002 → 新进程重新监听，无缝衔接。

## 错误处理

| 场景 | 行为 |
|---|---|
| gateway init 失败 | 警告降级，TUI/feishu 正常 |
| 3002 被占 | 警告降级，不起重复监听 |
| wake 事件处理中 TUI 退出 | shutdown 钩子关闭连接；v2 侧 notify 失败重试 3 次后落库 `notified=false` 待补发 |

## 测试

- **幂等守卫单测**：每个 init 连续调用 2 次不报错、效果不叠加（重点：`loadPlugins` 两次返回同一 registry、工具数不翻倍）
- **集成验证**：`npm run dev` 启动 → `curl 127.0.0.1:3002/wake/health` 通过 → 发测试 wake 事件（agent_reminder）处理成功 → TUI 交互正常互不影响 → Ctrl+C 退出后 3002 释放

## 明确不做（YAGNI）

- 不动旧 feishu.ts 实现，不切 gateway 版 feishu
- 不改 `npm run wake` 独立入口（保留作为 TUI 不在时的备选运行方式）
- 不改 gateway 内部（AgentGateway、session factory、syncer 保持现状）
- 不做事件补发机制（`notified=false` 审计保留现状）
