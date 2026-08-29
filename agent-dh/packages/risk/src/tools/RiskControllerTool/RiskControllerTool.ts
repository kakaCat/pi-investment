/**
 * RiskControllerTool - 风险控制工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { riskControllerPrompt, RiskControllerParams, RiskControllerResult } from './prompt';

/**
 * 风险控制工具类
 */
export class RiskControllerTool extends BaseTool<RiskControllerParams, RiskControllerResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'risk_controller',
    category: 'risk',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = riskControllerPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: RiskControllerParams): ValidationResult {
    if (!args.command) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'command',
        issue: 'command 是必填参数',
        expected: 'position_size / stop_loss / portfolio_risk',
      };
    }

    const validCommands = ['position_size', 'stop_loss', 'portfolio_risk'];
    if (!validCommands.includes(args.command)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'command',
        issue: `command 必须是 ${validCommands.join(' / ')} 之一`,
        received: args.command,
        expected: validCommands.join(' / '),
      };
    }

    // position_size 和 stop_loss 需要 symbol
    if ((args.command === 'position_size' || args.command === 'stop_loss') && !args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: `${args.command} 命令需要 symbol 参数`,
        expected: '6位股票代码，如 600519',
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: RiskControllerParams, _context: ToolContext): Promise<RiskControllerResult> {
    const result: any = await this.qv2.riskControl({
      command: args.command,
      symbol: args.symbol,
      account_name: args.account_name || 'agent_virtual',
      risk_level: args.risk_level,
    });

    return {
      command: args.command,
      symbol: args.symbol,
      result: result?.result ?? result,
      warning: result?.warning,
      ...result,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: RiskControllerResult, _context: ToolContext): ToolResponse<RiskControllerResult> {
    return {
      success: true,
      data: result,
    };
  }
}
