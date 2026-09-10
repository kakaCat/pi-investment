# :13080 实例 feishu_notify / notification_send 缺失根因与修复（2026-09-10）

**执行人**：investor / w-50fc8c52　**触发**：用户问"feishu_notify 在本会话工具集中不存在是什么原因，需要修复"
**性质**：配置分叉缺陷（非代码 bug），修复后已实测送达。

## 一、症状

R-010 规定"重要任务完成后调用 feishu_notify 主动通知用户"，但本实例（:13080 investment profile）自建立起，工具集中**从来没有** `feishu_notify` / `notification_send` / `notification_channels` 三个工具（`Object.keys(tools)` 126 项中无匹配），规则长期处于"无工具可调"空转状态。

## 二、根因：两份 patch 配置分叉，:13080 漏注册插件

| 检查项 | 结果 |
|---|---|
| 插件包 `agent-dh/packages/notification` | ✅ 存在，`src/index.ts` 注册 3 个工具 |
| profile `package.json` 依赖 | ✅ 有 `@pi-investment/notification` |
| profile `node_modules/@pi-investment/notification` | ✅ 符号链接存在 |
| **`~/.dsh-agent-dh/profiles/investment/cordis.patch.yml`** | ❌ **无 notification 条目** → 插件从未被加载 |
| `~/.dsh/profiles/investment/cordis.patch.yml`（:3080 主实例） | ✅ 有条目（第 185-192 行） |
| 该 profile 的历史备份（09-08 20:03 / 09-09 21:22 共 5 份） | `notification-hits=0`——**历来就没有**，不是本次改动删掉的 |

结论：包、依赖、链接三件齐备，**唯独 :13080 这份 patch 配置漏了插件注册**——:3080 有、:13080 没有的配置分叉。历史上的 `cordis.patch.yml.bak`（09-08 16:38）带通知块，但文件头自述"本文件（`~/.dsh`）为主实例(:3080)配置"，即 :13080 的配置是从缺该块的另一来源重建的。

## 三、修复

`~/.dsh-agent-dh/profiles/investment/cordis.patch.yml` 在 evolver 与 lifecycle 之间插入（与 :3080 / 仓库模板 `agent-dh/cordis.yml` 对齐）：

```yaml
- id: notification
  name: '@pi-investment/notification'
  config:
    agentOS:
      baseURL: http://localhost:8080
      agentId: agent-dh
    feishuWebhooks:            # 方案 C 降级兜底：Agent OS 主路径失败时直发飞书
      '*': https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-…
```

- 备份：`cordis.patch.yml.bak-notification-20260910-212859`（回退即覆盖回来再重启）
- 前置校验：`yaml.safe_load` 通过（43 顶层条目）；全仓仅 notification 包定义这三个工具名（无重复注册）；`agent-os-client`/`core-tool` 链接存在
- 生效方式：`self_restart`（插件在启动时加载，改配置必须重启）

## 四、验证（重启后，2026-09-10 21:29）

| 验证项 | 结果 |
|---|---|
| 工具注册 | `Object.keys(tools)` 126 → **129**，三工具全部出现 |
| 渠道发现（走 Agent OS） | `alerts/告警群`、`reports/报告群`、`trading/交易群` 均 enabled |
| 实测发送 | `feishu_notify(channel=reports, urgency=normal)` → `{success:true, delivery:'agent_os', log_id:'a97f449c-7690-4fab-a173-2e076eab4544'}` |
| 投递留痕 | `notification_channels(log_limit=3)` 首条即该消息，`status=sent`，`2026-09-10T21:29:51+08:00` |

## 五、遗留与建议

1. **webhook 兜底路径未实测**：验证走的是 Agent OS 主路径（`delivery=agent_os`）；要验证兜底需做故障注入（停 :8080 后再发）。建议纳入一次专项演练。
2. **缺"双实例配置差异巡检"**：本次是 `:3080` 与 `:13080` 两份 patch 分叉导致的能力缺失，且
**没有任何告警**——建议加一个巡检（比对两份 patch 的 `id` 集合差异 + 关键插件存在性），纳入盘后例程。
3. **模式教训**：工具"规则里写了、工具集里没有"这类缺失不会报错、不会失败，只会静默空转；凡"规则依赖某工具"处，应定期用 `Object.keys(tools)` 与规则引用清单对账。
