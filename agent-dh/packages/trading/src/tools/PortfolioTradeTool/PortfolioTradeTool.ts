/**
 * PortfolioTradeTool - 组合交易工具
 *
 * 继承 BaseTool，实现三个必须方法：
 * 1. validate - 校验参数
 * 2. execute - 执行交易
 * 3. wrap - 包装返回数据
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { portfolioTradePrompt, PortfolioTradeParams, PortfolioTradeResult } from './prompt';
import { assertTradingHours } from '../../utils/trading-hours';

export class PortfolioTradeTool extends BaseTool<PortfolioTradeParams, PortfolioTradeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'portfolio_trade',
    category: 'trading',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = portfolioTradePrompt;

  constructor(
    private qv2: QuantsysV2Client,
    private osMemory: any,
    private ctx: any  // Cordis context for tools.call
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: PortfolioTradeParams): ValidationResult {
    // 1. 检查 action
    if (!args.action) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 是必填参数',
        expected: 'BUY 或 SELL',
        example: 'BUY',
        guide: '请提供操作方向：BUY（买入）或 SELL（卖出）',
        commonMistakes: [
          '不要使用小写（buy/sell）',
          '不要使用中文（买入/卖出）',
        ],
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
        guide: '请使用大写的 BUY 或 SELL',
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
        guide: '请提供股票代码（6位数字）',
        commonMistakes: [
          '不要包含交易所前缀（如 SH600519）',
          '不要使用股票名称（如 贵州茅台）',
        ],
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
        guide: '请修正 symbol 参数。正确格式：6位数字（如 600519）',
        commonMistakes: [
          '不要包含交易所前缀（如 SH600519、SZ000001）',
          '不要使用股票名称（如 贵州茅台）',
          '不要包含点号（如 600519.SH）',
        ],
      };
    }

    // 3. 检查 quantity
    if (!args.quantity) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'quantity',
        issue: 'quantity 是必填参数',
        expected: '100的正整数倍',
        example: '100',
        guide: '请提供交易数量（必须是100的整数倍）',
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
        example: '100',
        guide: '请提供大于0的整数',
      };
    }

    if (args.quantity % 100 !== 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'quantity',
        issue: 'quantity 必须是100的整数倍（A股一手=100股）',
        received: String(args.quantity),
        expected: '100的整数倍',
        example: '100',
        guide: '请修正数量为100的整数倍（如 100、200、300）',
        commonMistakes: [
          '不要使用零头数量（如 50、150）',
          '不要使用负数',
        ],
      };
    }

    // 4. 检查 price（可选）
    if (args.price !== undefined && args.price !== null) {
      if (typeof args.price !== 'number' || args.price <= 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'price',
          issue: 'price 必须是正数',
          received: String(args.price),
          expected: '正数',
          example: '1850.0',
          guide: '请提供大于0的价格，或省略此参数使用市价成交',
        };
      }
    }

    // 5. 检查 execute_at（可选，2026-09-01 盘前挂单）
    if (args.execute_at !== undefined && args.execute_at !== 'market_open') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'execute_at',
        issue: "execute_at 仅支持 'market_open'（盘前挂单，开盘 9:31 起自动撮合）",
        received: String(args.execute_at),
        expected: "'market_open'",
        example: 'market_open',
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务（完整业务逻辑）
   */
  protected async execute(args: PortfolioTradeParams, _context: ToolContext): Promise<PortfolioTradeResult> {
    const accountName = args.account_name || 'agent_virtual';

    // 宪法第 1 条硬校验：非交易时段拒单。
    // 例外（2026-09-01）：execute_at='market_open' 盘前挂单——委托提交发生在盘前，
    // 但撮合执行由后端在开盘后 9:31 合法时段完成，不违反宪法（订单实际成交于交易时段）。
    const isPendingOrder = args.execute_at === 'market_open';
    if (!isPendingOrder) {
      assertTradingHours();
    }

    // R-008 决策前检索（M6，2026-08-27）：强制检索历史经验
    let experienceNote = '';
    if (args.reason && args.reason.includes('已检索')) {
      experienceNote = '✅ 已注明检索结论';
    } else {
      // 自动检索（辅助模式）
      try {
        const memResult: any = await this.osMemory.search({
          query: `${args.symbol} ${args.action}`,
          namespace: 'experience',
          top_k: 3,
        });

        const expCount = memResult?.memories?.length || 0;
        experienceNote = `⚠️  R-008: 已自动检索 ${expCount} 条经验`;

        // 如果有历史教训，在返回中提示
        if (expCount > 0 && !args.reason?.includes('已检索')) {
          experienceNote += `。建议在 reason 中注明："已检索：${expCount}条历史经验，${memResult.memories[0].title}"`;
        }
      } catch (e) {
        // 检索失败不阻塞交易（降级）
        experienceNote = '⚠️  R-008: 经验检索失败，降级放行';
      }
    }

    // M4-1 & M4-2 仓位映射与熔断校验（P1，2026-08-28）
    if (String(args.action).toUpperCase() === 'BUY') {
      const regimeLimitResult = await this.checkRegimePositionLimit(args, accountName);
      if (regimeLimitResult) {
        return { ...regimeLimitResult, r008_check: experienceNote } as any;
      }
    }

    // M2-2 排雷清单（2026-08-26）：买入前过滤问题股
    if (String(args.action).toUpperCase() === 'BUY') {
      const filterResult = await this.filterProblematicStocks(args.symbol);
      if (filterResult) {
        return { ...filterResult, r008_check: experienceNote } as any;
      }
    }

    // M5 滑点追踪（2026-08-25）：下单前抓决策时价
    let decisionPrice: number | undefined;
    let decisionTime: string | undefined;
    try {
      const q: any = await this.qv2.getQuote(args.symbol);
      if (Number(q?.price) > 0) {
        decisionPrice = Number(q.price);
        decisionTime = q?.timestamp ?? new Date().toISOString();
      }
    } catch { /* 行情获取失败不阻塞下单 */ }

    // 执行交易
    const genomeVersion = this.captureGenomeVersion();
    const result: any = await this.qv2.executeTrade({
      action: args.action.toLowerCase() as 'buy' | 'sell',
      symbol: args.symbol,
      quantity: args.quantity,
      price: args.price,
      account_name: accountName,
      order_type: args.price ? 'limit' : 'market',
      reason: args.reason,
      genome_version: genomeVersion,
      execute_at: args.execute_at,
      allow_duplicate: args.allow_duplicate === true ? true : undefined,
    });

    // 挂单未成交：不做信号/滑点追踪（成交发生在开盘撮合时，由盘后例程核对）
    if (result?.status === 'pending') {
      return {
        ...result,
        r008_check: experienceNote,
        pending_note: `挂单已受理（pending_order_id=${result.pending_order_id ?? result.order_id}），开盘后 9:31 起自动撮合；可用 trade_monitor 查挂单状态`,
      } as PortfolioTradeResult;
    }

    // M3-3 信号追踪（2026-08-26）：BUY 成交后自动记录信号
    if (String(args.action).toUpperCase() === 'BUY' && result && !result.error) {
      await this.trackSignal(args, result);
    }

    // M5 滑点计算与落库
    if (decisionPrice && Number(result?.price) > 0) {
      const slippageData = await this.trackSlippage(args, result, decisionPrice, decisionTime);
      return {
        ...result,
        slippage: slippageData,
        r008_check: experienceNote,
      } as PortfolioTradeResult;
    }

    return {
      ...result,
      r008_check: experienceNote,
    } as PortfolioTradeResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: PortfolioTradeResult, context: ToolContext): ToolResponse<PortfolioTradeResult> {
    // 2026-09-01 修复：拦截/拒单结果（blocked、success=false）不带 order_id，
    // 原实现一律报 OUTPUT_ERROR 把拦截原因吞掉（熔断/仓位超限/排雷拦截都显示成
    // "缺少必需字段"的内部错误）。拦截属于正常业务结果，直接透传 reason。
    const r: any = result;
    if (r && (r.blocked || r.success === false)) {
      return {
        success: false,
        data: result,
        message: r.reason ?? r.error ?? '交易被拦截',
        error: {
          success: false,
          errorType: ErrorType.BUSINESS_REJECTION,
          issue: r.reason ?? r.error ?? '交易被拦截',
          guide: r.blocked ? '交易被风控规则拦截，这是正常的风控行为' : undefined,
        } as any,
      };
    }

    // 检查必需字段
    if (!result.order_id || !result.symbol || !result.status) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          issue: '返回数据缺少必需字段（order_id, symbol, status）',
          guide: '这是内部错误，请联系开发者',
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }

  /**
   * M4-1 & M4-2: 仓位映射与熔断校验
   */
  private async checkRegimePositionLimit(args: PortfolioTradeParams, accountName: string): Promise<any | null> {
    try {
      // 调用 regime_position_limit 工具获取仓位限制和熔断状态
      // 2026-09-01 修复：ToolRuntime 没有 call() 方法（原写法必抛 TypeError，
      // 被 catch 兜底成"仓位校验失败"保守拒单——8-28 起所有到达此处的 BUY
      // 实际都被误拦，只是此前多数调用更早被交易时段/参数校验挡下未暴露）。
      // 正确入口：ctx.tools.execute({name, arguments, signal})，取 result.value。
      const r: any = await (this.ctx.tools as any).execute({
        name: 'regime_position_limit',
        arguments: { account_name: accountName },
        signal: new AbortController().signal,
      });
      if (r?.isError) {
        throw new Error(r?.error?.message || 'regime_position_limit 调用失败');
      }
      const regimeLimit: any = r?.value ?? r;

      // 检查熔断状态（M4-2）
      if (regimeLimit.verdict === 'circuit_breaker') {
        return {
          success: false,
          blocked: true,
          reason: `熔断激活：${regimeLimit.circuit_breaker?.action || '60日最大回撤超8%，禁止新开仓'}`,
          circuit_breaker: regimeLimit.circuit_breaker,
          regime_limit: regimeLimit,
        };
      }

      // 检查当前仓位是否已超限（M4-1）
      if (regimeLimit.verdict === 'reduce_required') {
        return {
          success: false,
          blocked: true,
          reason: `仓位超限：当前 ${regimeLimit.current_position_pct}% 已超 ${regimeLimit.regime}(${regimeLimit.max_position_pct}%) 上限，须减仓至 ${regimeLimit.reduce_to_pct}%`,
          regime: regimeLimit.regime,
          verdict: regimeLimit.verdict,
          regime_limit: regimeLimit,
        };
      }

      // 预判买入后仓位
      const buyValue = (args.price || 0) * args.quantity;
      if (buyValue > 0 && regimeLimit.current_position_pct > 0) {
        const summary: any = await this.qv2.getPortfolioSummary(accountName);
        const totalAsset = Number(summary?.totalValue ?? 0);

        // 获取实际买入价格（如未传入）
        let actualBuyValue = buyValue;
        if (!args.price && totalAsset > 0) {
          try {
            const q: any = await this.qv2.getQuote(args.symbol);
            if (Number(q?.price) > 0) {
              actualBuyValue = Number(q.price) * args.quantity;
            }
          } catch { /* 行情获取失败保守降级 */ }
        }

        // 计算买入后仓位比例
        if (actualBuyValue > 0 && totalAsset > 0) {
          const afterBuyPct = regimeLimit.current_position_pct + ((actualBuyValue / totalAsset) * 100);

          if (afterBuyPct > regimeLimit.max_position_pct) {
            // 记录拦截到 osMemory
            try {
              await this.osMemory.write({
                title: `M4-1 仓位映射拦截：${args.symbol}`,
                content: JSON.stringify({
                  symbol: args.symbol,
                  regime: regimeLimit.regime,
                  regime_limit_pct: regimeLimit.max_position_pct,
                  current_position_pct: regimeLimit.current_position_pct,
                  buy_value: actualBuyValue,
                  position_after_buy_pct: afterBuyPct,
                  blocked: true,
                  reason: `买入后仓位将达 ${afterBuyPct.toFixed(1)}%，超 ${regimeLimit.regime}(${regimeLimit.max_position_pct}%) 上限`,
                  timestamp: new Date().toISOString(),
                }),
                namespace: 'risk',
                tags: ['m4', 'regime_position_block', regimeLimit.regime, args.symbol],
              });
            } catch { /* 落库失败不影响拦截决策 */ }

            return {
              success: false,
              blocked: true,
              reason: `买入后仓位将达 ${afterBuyPct.toFixed(1)}%，超 ${regimeLimit.regime}(${regimeLimit.max_position_pct}%) 上限`,
              regime: regimeLimit.regime,
              regime_limit: regimeLimit,
              current_position_pct: regimeLimit.current_position_pct,
              position_after_buy_pct: afterBuyPct.toFixed(1),
            };
          }

          // 校验通过，记录留痕
          try {
            await this.osMemory.write({
              title: `M4-1 仓位映射校验通过：${args.symbol}`,
              content: JSON.stringify({
                symbol: args.symbol,
                regime: regimeLimit.regime,
                regime_limit_pct: regimeLimit.max_position_pct,
                current_position_pct: regimeLimit.current_position_pct,
                buy_value: actualBuyValue,
                position_after_buy_pct: afterBuyPct,
                blocked: false,
                timestamp: new Date().toISOString(),
              }),
              namespace: 'risk',
              tags: ['m4', 'regime_position_check', regimeLimit.regime, args.symbol],
            });
          } catch { /* 落库失败不阻塞交易 */ }
        }
      }

      return null; // 校验通过
    } catch (e: any) {
      // regime_position_limit 工具调用失败，保守降级：拒绝交易
      return {
        success: false,
        blocked: true,
        reason: `仓位校验失败：${e.message}。保守原则：调用 regime_position_limit 失败时拒绝买入`,
        error: e.message,
      };
    }
  }

  /**
   * RFC 005 决策打标：捕获当前基因组版本（与 learning 插件 captureGenomeContext 同法）。
   * 只读容错——拿不到 genome 不阻塞下单，成交记录 genome_version 为 NULL。
   */
  private captureGenomeVersion(): string | undefined {
    try {
      // @ts-ignore - genome 插件通过 inject 动态注入
      const genome = this.ctx?.genome;
      return genome?.genomeData?.genome_version ?? undefined;
    } catch {
      return undefined;
    }
  }

  /**
   * M2-2: 排雷清单 - 过滤问题股
   */
  private async filterProblematicStocks(symbol: string): Promise<any | null> {
    // 1. ST 禁区
    if (symbol.includes('ST')) {
      return {
        success: false,
        blocked: true,
        reason: 'ST 禁区：ST/*ST 股票禁止买入（交易宪法第 5 条）',
        rule: 'M2-2-ST',
      };
    }

    // 2. 操纵嫌疑检测
    try {
      const { detectManipulation } = await import('@pi-investment/quantsys-v2-client');
      const manipResult = await detectManipulation(this.qv2, symbol, 30);
      const suspicionScore = Number(manipResult?.manipulation_score || 0);

      if (suspicionScore > 70) {
        // 拒绝交易 + 落库留痕
        await this.osMemory.write({
          title: `M2-2 操纵嫌疑拦截：${symbol}`,
          content: JSON.stringify({
            symbol,
            suspicion_score: suspicionScore,
            risk_level: manipResult?.risk_level,
            detected_patterns: manipResult?.detected_patterns,
            evidence: manipResult?.evidence,
            blocked: true,
            reason: `操纵嫌疑评分 ${suspicionScore.toFixed(1)} >70，禁止买入`,
            timestamp: new Date().toISOString(),
          }),
          namespace: 'risk',
          tags: ['m2', 'manipulation_block', symbol],
        });

        return {
          success: false,
          blocked: true,
          reason: `操纵嫌疑：嫌疑评分 ${suspicionScore.toFixed(1)} >70，禁止买入（genome 标的禁区）`,
          suspicion_score: suspicionScore,
          detected_patterns: manipResult?.detected_patterns,
          evidence: manipResult?.evidence,
          rule: 'M2-2-manipulation',
        };
      }
    } catch (e: any) {
      // 检测失败不阻塞交易（保守：允许，但记录警告）
      await this.osMemory.write({
        title: `M2-2 操纵检测失败：${symbol}`,
        content: JSON.stringify({
          symbol,
          error: e.message || 'manipulation_detect 调用失败',
          action: '允许交易（保守原则）',
          timestamp: new Date().toISOString(),
        }),
        namespace: 'risk',
        tags: ['m2', 'manipulation_detect_error', symbol],
      });
    }

    return null; // 校验通过
  }

  /**
   * M3-3: 信号追踪 - BUY 成交后自动记录信号
   */
  private async trackSignal(args: PortfolioTradeParams, result: any): Promise<void> {
    try {
      const inferSource = (reason: string): string => {
        if (!reason) return 'manual';
        if (reason.includes('strategy_execute')) return 'strategy_execute';
        if (reason.includes('opportunity_scan')) return 'opportunity_scan';
        if (reason.includes('mainline_stocks')) return 'mainline_stocks';
        if (reason.includes('watch_rule')) return 'watch_rule';
        return 'manual';
      };

      const inferGrade = (reason: string): 'A' | 'B' | 'C' => {
        if (!reason) return 'C';
        if (reason.includes('A级') || reason.includes('(A)')) return 'A';
        if (reason.includes('B级') || reason.includes('(B)')) return 'B';
        return 'C';
      };

      await (this.ctx.tools as any).execute({
        name: 'signal_track',
        arguments: {
          action: 'record',
          symbol: args.symbol,
          price: result.price || args.price,
          source: inferSource(args.reason || ''),
          grade: inferGrade(args.reason || ''),
          reason: args.reason || '',
        },
        signal: new AbortController().signal,
      });
    } catch (e: any) {
      // 信号记录失败不影响交易结果
      console.error(`signal_track record 失败: ${e.message}`);
    }
  }

  /**
   * M5: 滑点追踪 - 计算并落库
   */
  private async trackSlippage(
    args: PortfolioTradeParams,
    result: any,
    decisionPrice: number,
    decisionTime?: string
  ): Promise<any> {
    const fillPrice = Number(result?.price);
    if (!fillPrice || fillPrice <= 0) return null;

    // 方向归一：滑点为正 = 比决策时价更差（买贵/卖便宜）
    const dirSign = String(args.action).toUpperCase() === 'SELL' ? -1 : 1;
    const slipPct = +(((fillPrice - decisionPrice) / decisionPrice * 100) * dirSign).toFixed(3);

    try {
      await this.osMemory.createMemory({
        kind: 'episode',
        scope: 'trade:slippage',
        title: `slippage ${args.symbol} ${args.action} ${slipPct}%`,
        content: `滑点记录：${args.symbol} ${args.action} ${args.quantity}股，决策时价 ${decisionPrice}（${decisionTime}）→ 成交 ${fillPrice}，滑点 ${slipPct}%。理由：${args.reason ?? '未填'}`,
        payload: {
          symbol: args.symbol,
          action: args.action,
          quantity: args.quantity,
          decision_price: decisionPrice,
          fill_price: fillPrice,
          slippage_pct: slipPct,
          decision_time: decisionTime,
          order_id: result?.order_id ?? null,
          ts: new Date().toISOString(),
        },
        status: 'testing',
        confidence: 0.8,
        source: 'trade_slippage',
        provenance: { channel: 'dsh', session_kind: 'agent' },
      });
    } catch { /* 落库失败不影响交易 */ }

    return {
      decision_price: decisionPrice,
      fill_price: fillPrice,
      slippage_pct: slipPct,
      decision_time: decisionTime,
    };
  }
}
