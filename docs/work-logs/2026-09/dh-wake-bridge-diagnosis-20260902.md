# dh /wake 唤醒桥状态确认与服务报错诊断（2026-09-02）

> 窗口：w-8366e526（investor） | 分支：agent-self/20260902-110540 | 提交：6610e46a

## 背景

quantsys-v2 的 `AgentNotificationService` 通过 `POST {AGENT_API_URL}/wake`（body: `{event,data,timestamp}`，头 `X-Wake-Token`）唤醒 dh 以推送提醒。此前 dh 侧无 `/wake` 路由形成死链，本次任务目标为实现该路由并打通 v2→dh→飞书链路（路 2）。

## 交付内容（已提交 6610e46a，git 确认无回退）

| 工件 | 状态 | 位置 |
|---|---|---|
| wake-webhook 路由 | ✅ 已提交 | `agent-dh/packages/lifecycle/src/wake-webhook.ts` |
| lifecycle 注册 `/wake` + wakeToken 配置 | ✅ 已提交 | `agent-dh/packages/lifecycle/src/index.ts` |
| 生产 wakeToken | ✅ 完好（L137） | `~/.dsh-agent-dh/profiles/investment/cordis.patch.yml` |
| v2 → dh 指向与 token | ✅ 完好（L38/39） | `quantsys-v2/.env` |

鉴权协议：`wakeToken` == v2 `AGENT_API_TOKEN` == `6355bfeb70d51ddf1eacd54683228c31`。
语义：deliver 抛错 → 200 `{success:false}`（v2 会重试）；token 不匹配 → 401；非 POST → 405；非 JSON → 415；超限 body → 413。

## "服务报错 / 退回了一些内容"诊断结论（用户报告，已查清）

用户反馈"更改后导致服务报错，现在退回了一些内容"。逐一核查后结论：**本次 wake 交付的 4 项工件全部完好，git 13:29 后无任何 reset/checkout/rollback**。所谓"退回"与"报错"另有来源：

1. **外部会话两波批量改动（非本窗口）**
   - 13:36 / 16:03：外部会话批量修改 15 个 agent-dh 包 `src/index.ts`（相对 import 加 `/index.js` 后缀，124/124 对称行，纯工作区未提交）——与 wake 无关。
   - 13:42 / 13:46：给**两份** cordis.patch.yml（`~/.dsh` 副本与 `~/.dsh-agent-dh` 生产）都加了禁用块：`tool-subagent-report`、`api-gateway` disabled，注释注明"DSH 0.1.1-rc.2 中这些插件依赖不存在的 API"。两次编辑措辞不同 = 两独立操作。

2. **launchd 反复拉起风暴（"服务报错"的最可能来源）**
   - `~/.dsh/profiles/investment/state/launchd.out.log`：19:36–19:47 间 **11 次反复启动**（rc.2 ×10 段 → 最后 rc.8），launchctl 显示上次退出码 **-9（SIGKILL）**。
   - 19:47:37 起 PID **7586**（launchd 托管，PPID=1）稳定接管 :13080，运行至今健康。
   - 19:49 `~/.dsh` 副本 node_modules 被重建为 **0.1.2-alpha.5**（磁盘版本与运行进程漂移，混合态隐患，非本次改动所致）。

3. **运行底座切换**：13:46 外部会话手动启动的生产实例（PID 81839，alpha.4，/wake 曾验证 200）已退出；当前 :13080 由 launchd 拉起的 `~/.dsh` 副本实例（rc 系启动、配置读生产 DSH_HOME）接管。live 配置实际仍含 wakeToken，故鉴权生效。

## 当前实测状态（诊断收尾时复测）

- `POST /wake` 带正确 token → **200 `{"success":true}`**（多轮复测稳定）
- `POST /wake` 无 token → 401 invalid wake token（鉴权生效）
- 实例 PID 7586 存活健康，lifecycle 插件 symlink 至 agent-dh 源码（wake 代码实际被加载运行）

## 决策

用户选定：**保持现状，wake 链路已通，不再改动**。仅补本文档与通知收尾。

## 遗留关注（不改动，仅记录）

- `~/.dsh`（launchd 托管）与 `~/.dsh-agent-dh`（生产）两套 profile 并存；当前运行底座是 `~/.dsh` 副本（rc 系/alpha.5 磁盘），配置经 start.sh 强制 `DSH_HOME=~/.dsh-agent-dh` 读取生产。未来若需统一版本或消除漂移，需人工决策（本次不动）。
- launchd plist `com.pi-investment.dsh` 指向 `~/.dsh/profiles/investment/start.sh`，KeepAlive=true——任何"想让生产配置成为 live"的操作须改 plist 指向或停用 launchd 托管，勿用 self_restart（restarter 同样会拉起 `~/.dsh` 副本）。
- 禁用块（tool-subagent-report / api-gateway）为外部会话所加，未核实其意图，本次未动。
