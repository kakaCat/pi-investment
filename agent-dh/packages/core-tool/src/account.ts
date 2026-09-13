/**
 * 账户单一事实源（2026-09-13 w-c8cae280）
 *
 * 背景：本实例的投资账户名曾在 ~30 处代码与 13 个 Agent OS 例行任务的 prompt 里各自写死
 * （最早是 agent_virtual = agent-ts 的账户），换账户要改 N 个地方、漏一处就"用别人的账下单"
 * ——这正是 R-019 的由来。现收敛为**一处定义**：
 *
 *   - 任务/提示词侧的事实源 = profileDir/agents.json 的 instance.account（由 lifecycle 注入系统提示词）；
 *   - 代码侧的默认值 = 本常量（可用环境变量 DSH_INVESTMENT_ACCOUNT 覆盖，无需改代码）。
 *
 * 纪律：工具默认值只是兜底，写操作仍必须显式传 account_name（R-019③）。
 */
export const DEFAULT_AGENT_ACCOUNT = ((): string => {
  try {
    const env = typeof process !== 'undefined' ? process.env?.DSH_INVESTMENT_ACCOUNT : undefined;
    return (env && String(env).trim()) || 'agent_brain';
  } catch {
    return 'agent_brain';
  }
})();
