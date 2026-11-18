import { BaseTool, ErrorType, DEFAULT_AGENT_ACCOUNT, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { evaluationReportPrompt, EvaluationReportParams } from './prompt';

export class EvaluationReportTool extends BaseTool<EvaluationReportParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'evaluation_report',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = evaluationReportPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: EvaluationReportParams): ValidationResult {
    for (const field of ['start_date', 'end_date'] as const) {
      if (args[field] && !/^\d{4}-\d{2}-\d{2}$/.test(args[field]!)) {
        return { success: false, errorType: ErrorType.INPUT_ERROR, issue: `${field} 格式须为 YYYY-MM-DD` };
      }
    }
    const rate = args.annual_cost_rate ?? 0.02;
    if (typeof rate !== 'number' || !Number.isFinite(rate) || rate < 0 || rate > 1) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, issue: 'annual_cost_rate 须为 0~1 的有限数值' };
    }
    return { success: true };
  }

  protected async execute(args: EvaluationReportParams, _context: ToolContext): Promise<any> {
    const accountName = args.account_name?.trim() || DEFAULT_AGENT_ACCOUNT;
    const report = await this.qv2.getInvestmentEvaluationReport({
      account_name: accountName,
      start_date: args.start_date,
      end_date: args.end_date,
      annual_cost_rate: args.annual_cost_rate ?? 0.02,
    });
    const { intervals: _intervals, ...accountEconomy } = report.accountEconomy || {};
    const value: any = {
      ...report,
      accountEconomy,
      tradeLedgerOmitted: !args.include_ledger,
    };
    if (!args.include_ledger) delete value.tradeLedger;
    return sanitizeLossless(value);
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
