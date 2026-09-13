/**
 * AlgoExecuteTool - 算法交易工具
 */

import { BaseTool, ErrorType, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { algoExecutePrompt, AlgoExecuteParams, AlgoExecuteResult } from './prompt';

/**
 * 算法交易工具类
 */
export class AlgoExecuteTool extends BaseTool<AlgoExecuteParams, AlgoExecuteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'algo_execute',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = algoExecutePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: AlgoExecuteParams): ValidationResult {
    // 1. 检查 action
    if (!args.action) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 是必填参数',
        expected: 'BUY 或 SELL',
        example: 'BUY',
      };
    }

    if (!['BUY', 'SELL'].includes(args.action)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 必须是 BUY 或 SELL',
        received: args.action,
        expected: 'BUY 或 SELL',
        example: 'BUY',
      };
    }

    // 2. 检查 symbol
    if (!args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 是必填参数',
        expected: '6位数字股票代码',
        example: '600519',
      };
    }

    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位数字股票代码',
        received: args.symbol,
        expected: '6位数字',
        example: '600519',
      };
    }

    // 3. 检查 quantity
    if (!args.quantity) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'quantity',
        issue: 'quantity 是必填参数',
        expected: '正整数',
        example: '1000',
      };
    }

    if (!Number.isInteger(args.quantity) || args.quantity <= 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'quantity',
        issue: 'quantity 必须是正整数',
        received: String(args.quantity),
        expected: '正整数',
        example: '1000',
      };
    }

    // 4. 检查 algo（可选）
    if (args.algo !== undefined && args.algo !== null) {
      if (!['TWAP', 'VWAP'].includes(args.algo)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'algo',
          issue: 'algo 必须是 TWAP 或 VWAP',
          received: args.algo,
          expected: 'TWAP 或 VWAP',
          example: 'TWAP',
        };
      }
    }

    // 5. 检查 duration（可选）
    if (args.duration !== undefined && args.duration !== null) {
      if (!Number.isInteger(args.duration) || args.duration <= 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'duration',
          issue: 'duration 必须是正整数',
          received: String(args.duration),
          expected: '正整数（分钟）',
          example: '30',
        };
      }
    }

    // 2026-09-13（w-c8cae280）：补整手校验（宪法第2条：A股买入 100 股整数倍）。
    // 实测原先 quantity=150 也放行，并生成"15 股/片"这种 A 股不可能成交的切片计划。
    if (Number(args.quantity) % 100 !== 0) {
      return {
        success: false,
        errorType: 'INPUT_ERROR' as any,
        field: 'quantity',
        issue: 'quantity 必须是100的整数倍（A股一手=100股，宪法第2条）',
        received: String(args.quantity),
        expected: '100 的整数倍',
        example: '100',
      };
    }

    // 2026-09-13（用户裁定）：不做拦截——account_name 缺参时按工具层默认账户执行
    // （agent-dh = DEFAULT_AGENT_ACCOUNT = agent_brain；agent-ts 侧各自维护自己的默认值）。
    // 账户名不写死：任务/文档引用系统提示词 agent:identity 段的「本实例投资账户」。
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: AlgoExecuteParams, _context: ToolContext): Promise<AlgoExecuteResult> {
    // ⚠️ 2026-09-13（w-c8cae280）实测结论，改动前必读：
    // 后端 POST /api/orders/algo-execute **只生成 TWAP/VWAP 切片计划，从不下单** ——
    // 实测（agent_brain，非交易日）：返回 algo_order_id/filled_quantity=0/slices=pending，
    // 而现金变动 0、持仓不变、挂单 0；实现里没有交易服务调用、没有资金/持仓校验、没过 trade_guard。
    // 因此本工具**不是执行器**：调用它不会产生任何成交。
    // 交易时段闸门此前被注释掉（原因即"它不下单"），但这留下一个陷阱：
    //   * 工具名/描述像执行器，"成功"返回也像已受理 → agent 会误以为大单在分批执行；
    //   * 一旦后端将来真的下单，这里没有闸门 = 宪法第1条失守。
    // 故：① 本工具改为**计划语义**（下方 wrap 显式标注 executed=false）；
    //     ② 补整手校验（宪法第2条，A股 100 股整数倍——原先 quantity=150 也放行）；
    //     ③ 真实执行落地时必须同时补 assertTradingHours()（TODO 与后端实现一起做）。
    // 整手校验在 validate()（Phase 1）里做 —— execute 必须返回 AlgoExecuteResult，不能返回校验错误。
    const result = await this.qv2.executeAlgo({
      side: args.action.toLowerCase() as 'buy' | 'sell',
      symbol: args.symbol,
      quantity: args.quantity,
      algo: args.algo || 'TWAP',
      duration: args.duration || 30,
      account_name: args.account_name || DEFAULT_AGENT_ACCOUNT,
    });
    return result as unknown as AlgoExecuteResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: AlgoExecuteResult, _context: ToolContext): ToolResponse<AlgoExecuteResult> {
    // 2026-09-13（w-c8cae280）：显式声明"未执行"。后端只回切片计划，filled_quantity 恒 0——
    // 不标注的话，返回体（有 algo_order_id、status、slices）与"已受理的算法单"无法区分。
    const _r: any = result as any;
    if (_r && typeof _r === 'object') {
      const filled = Number(_r.filled_quantity ?? 0);
      _r.executed = false;
      _r.plan_only_note =
        '本工具只生成切片计划，未产生任何成交（filled_quantity=' + filled + '）。' +
        '需要真实成交请用 portfolio_trade（可分多次下真实单）；' +
        '后端 algo-execute 目前不接交易服务、不过 trade_guard。';
    }
    // 检查必需字段
    const requiredFields = ['algo_order_id', 'symbol', 'total_quantity', 'status'];
    const missingFields: string[] = [];

    for (const field of requiredFields) {
      if (result[field as keyof AlgoExecuteResult] === undefined) {
        missingFields.push(field);
      }
    }

    if (missingFields.length > 0) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: missingFields.join(', '),
          issue: `返回数据缺少必需字段`,
          expected: `包含所有必需字段: ${requiredFields.join(', ')}`,
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}
