/**
 * account_list 工具定义（2026-09-13 w-c8cae280）
 *
 * 动机（用户提问："账户信息可以查询吗"）：后端早就有 GET /api/simulation/accounts（账户发现），
 * 但工具层没接 —— 于是模型只能靠提示词/记忆知道账户名，这正是"账户名被写死"的土壤。
 * 本工具把账户发现接进工具层：先查有哪些账、哪个是本实例账户，再决定操作谁。
 */

export interface AccountListParams {
  /** active（默认）| all */
  status?: string;
}

export interface AccountListResult {
  accounts: Array<Record<string, any>>;
  total: number;
  default_account: string;
  default_account_source: string;
}

export const accountListPrompt = {
  name: 'account_list',
  description:
    '账户清单（只读）：列出后端全部模拟账户及其摘要（类型/状态/总资产/现金/持仓数/累计收益），并标出本实例的投资账户。'
    + '用于：①"我该操作哪个账"——不必把账户名写死在任务或代码里；②排查"这笔单打到谁的账上"；'
    + '③多系统（agent-dh / agent-ts）共用同一后端时的账户发现。查看单个账户的详细资产用 account_info，看持仓明细用 position_list。',
  parameters: {
    status: {
      type: 'string',
      description: "账户状态过滤：active（默认，在册账户）| all（含已归档/冻结的历史账户）",
      example: 'active',
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        accounts: {
          type: 'array',
          description: '账户清单（original snake_case 字段 + is_default_account 标记）',
          items: {
            type: 'object',
            additionalProperties: true,
            properties: {
              account_name: { type: 'string', description: '账户名（工具调用时传它）' },
              display_name: { type: 'string', description: '中文名' },
              account_type: { type: 'string', description: 'agent / strategy / user / legacy' },
              status: { type: 'string', description: 'active / archived / frozen' },
              total_value: { type: 'number', description: '总资产' },
              cash_available: { type: 'number', description: '可用现金' },
              position_value: { type: 'number', description: '持仓市值' },
              cumulative_return: { type: 'number', description: '累计收益率（小数）' },
              positions_count: { type: 'number', description: '持仓只数' },
              is_default_account: { type: 'boolean', description: '是否为本实例默认投资账户' },
            },
          },
        },
        total: { type: 'number', description: '账户数' },
        default_account: { type: 'string', description: '本实例默认投资账户（工具层常量）' },
        default_account_source: { type: 'string', description: '默认账户的来源说明' },
      },
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
} as const;
