/**
 * RiskControllerTool - 风险控制工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import { sanitizeLossless } from '@pi-investment/core-tool';
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

    // position_size 需要 price
    if (args.command === 'position_size' && !args.price) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'price',
        issue: 'position_size 命令需要 price 参数',
        expected: '当前价格',
      };
    }

    // stop_loss 需要 entry_price
    if (args.command === 'stop_loss' && !args.entry_price) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'entry_price',
        issue: 'stop_loss 命令需要 entry_price 参数',
        expected: '入场价格',
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: RiskControllerParams, _context: ToolContext): Promise<RiskControllerResult> {
    const raw: any = await this.qv2.riskControl({
      command: args.command,
      symbol: args.symbol,
      account_name: args.account_name || 'agent_virtual',
      risk_level: args.risk_level,
      price: args.price,
      entry_price: args.entry_price,
    });

    const sanitized: Record<string, any> = {};
    for (const [k, v] of Object.entries(raw ?? {})) {
      if (v !== undefined && v !== null && !(typeof v === 'number' && Number.isNaN(v))) {
        sanitized[k] = v;
      }
    }

    // 2026-08-30 修复：显式 warning: undefined 会导致 JSON 往返不等（lossless 校验失败）。
    // 不再无条件写入 warning 键；result 也做递归无损清洗。
    // 2026-08-30 二次修复：out 顶层若含 undefined 键（如 portfolio_risk 的 symbol），
    // DSH snapshotJsonValue 会拒绝整个值（"value must be an object"），
    // 因此整个 out 再过一遍 sanitizeLossless 删除 undefined 键。
    const out: Record<string, any> = sanitizeLossless({
      command: args.command,
      symbol: args.symbol,
      result: sanitizeLossless(sanitized.result ?? sanitized),
      ...sanitized,
    }) as Record<string, any>;
    return out as RiskControllerResult;
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
