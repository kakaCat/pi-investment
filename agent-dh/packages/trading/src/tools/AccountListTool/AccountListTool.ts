/**
 * AccountListTool - 账户清单（只读）
 *
 * 2026-09-13（w-c8cae280）：把后端的"账户发现"接口接进工具层，让 agent 能**查询**账户，
 * 而不是把账户名写死在提示词里。
 */
import { BaseTool, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { accountListPrompt, AccountListParams, AccountListResult } from './prompt';

export class AccountListTool extends BaseTool<AccountListParams, AccountListResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'account_list',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = accountListPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: AccountListParams): ValidationResult {
    if (args.status !== undefined && args.status !== null && !['active', 'all'].includes(String(args.status))) {
      return {
        success: false,
        errorType: 'INPUT_ERROR' as any,
        field: 'status',
        issue: "status 只能是 active 或 all",
        received: args.status,
        expected: 'active | all',
      };
    }
    return { success: true };
  }

  protected async execute(args: AccountListParams, _context: ToolContext): Promise<AccountListResult> {
    const status = (args.status as string) || 'active';
    const rows = await this.qv2.listAccounts(status as any);
    const accounts = (rows || []).map((a: any) => ({
      ...a,
      is_default_account: String(a?.account_name) === DEFAULT_AGENT_ACCOUNT,
    }));
    return {
      accounts,
      total: accounts.length,
      default_account: DEFAULT_AGENT_ACCOUNT,
      default_account_source:
        '工具层默认值 core-tool 的 DEFAULT_AGENT_ACCOUNT（环境变量 DSH_INVESTMENT_ACCOUNT 可覆盖）；'
        + '任务/提示词侧的事实源是 profileDir/agents.json 的 instance.account（见系统提示词 agent:identity 段）',
    };
  }

  protected wrap(result: AccountListResult, _context: ToolContext): ToolResponse<AccountListResult> {
    return { success: true, data: result };
  }
}
