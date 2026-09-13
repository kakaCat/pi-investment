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

  constructor(private qv2: QuantsysV2Client, private osMemory?: any) {
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
      account_name: args.account_name || 'agent_brain',
      risk_level: args.risk_level,
      price: args.price,
      entry_price: args.entry_price,
    });

    // 2026-09-13（w-c8cae280）R-006 余量感知：position_size 叠加 regime 余量钳制。
    // 后端只按"账户价值 × 风险比"给静态建议（实测恒为 totalValue×20%、accountValue 写死 100000），
    // 既不读 regime 仓位上限、也不读当前敞口——实测 agent_brain 敞口 14.2%、上限 40%、
    // 余量 25.8pp 时，它仍建议单笔 20000 元（=20% 硬顶），等于把 25.8pp 的余量当空气。
    // 现口径：可下上限 = min(单股 20% 硬顶, regime 剩余可加仓金额)，并把两个来源都摆出来。
    if (args.command === 'position_size') {
      const accountName = args.account_name || 'agent_brain';
      const extra: Record<string, any> = {};
      try {
        const [regimeRes, summary] = await Promise.all([
          this.osMemory
            ? this.osMemory.searchMemory({ q: 'regime', scope: 'market:regime', limit: 10 })
            : Promise.resolve({ items: [] }),
          this.qv2.getPortfolioSummary(accountName),
        ]);
        const CAPS: Record<string, number> = { panic: 100, risk_on: 80, sideways: 60, risk_off: 40, euphoria: 30 };
        const latest = ((regimeRes as any)?.items || [])
          .filter((it: any) => it.status !== 'deprecated' && it.payload?.date)
          .sort((a: any, b: any) => String(b.payload.date).localeCompare(String(a.payload.date)))[0];
        const regime = latest?.payload?.regime ?? 'sideways';
        const quality = latest?.payload?.evidence?.data_quality ?? 'unknown';
        const conflicts = latest?.payload?.evidence?.conflicts ?? null;
        const rawCap = CAPS[regime] ?? 60;
        let cap = rawCap;
        let capNote = '';
        if ((quality === 'degraded' || (Array.isArray(conflicts) && conflicts.length > 0)) && cap > 60) {
          cap = 60;
          capNote = `数据降级（${quality}），上限由 ${rawCap}% 收紧至 60%`;
        }
        const totalValue = Number((summary as any)?.totalValue ?? 0);
        const marketValue = Number((summary as any)?.totalMarketValue ?? 0);
        const currentPct = totalValue > 0 ? +(marketValue / totalValue * 100).toFixed(1) : 0;
        const headroomPct = +Math.max(0, cap - currentPct).toFixed(1);
        const headroomAmount = Math.floor(totalValue * headroomPct / 100);
        const staticSize = Number((raw as any)?.result?.recommendedSize ?? (raw as any)?.recommendedSize ?? 0);
        const recommendedSize = Math.min(staticSize, headroomAmount);
        extra.accountValueUsed = totalValue;
        extra.regime = regime;
        extra.regimeCapPct = cap;
        extra.regimeCapNote = capNote;
        extra.currentPositionPct = currentPct;
        extra.headroomPct = headroomPct;
        extra.headroomAmount = headroomAmount;
        extra.staticRecommendedSize = staticSize;
        extra.recommendedSize = recommendedSize;
        extra.cappedBy = recommendedSize < staticSize ? 'regime_headroom' : 'single_stock_cap';
        extra.source = 'risk_controller(position_size) 与 regime_position_limit 同口径合并（w-c8cae280，2026-09-13）';
        if (!latest) extra.regimeNote = '无 regime 记录，按震荡档 60% 保守取值（R-006）';
        if ((raw as any)?.result && typeof (raw as any).result === 'object') Object.assign((raw as any).result, extra);
        else (raw as any).result = extra;
        if ((raw as any)?.recommendedSize !== undefined) (raw as any).recommendedSize = recommendedSize;
      } catch (e: any) {
        extra.headroomNote =
          `余量校验降级（${String(e?.message || e).slice(0, 80)}）：recommendedSize 仅为静态建议，未做 regime 余量钳制`;
        if ((raw as any)?.result && typeof (raw as any).result === 'object') Object.assign((raw as any).result, extra);
      }
    }

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
