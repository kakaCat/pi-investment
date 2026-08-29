/**
 * RegimeDailyTool - 市场 Regime 每日落库工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { regimeDailyPrompt, RegimeDailyParams, RegimeDailyResult } from './prompt';

interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
  createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }>;
}

/**
 * Regime 每日落库工具类
 */
export class RegimeDailyTool extends BaseTool<RegimeDailyParams, RegimeDailyResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'regime_daily',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 60000, // 情绪接口偶发慢调用，放宽
  };

  protected readonly prompt = regimeDailyPrompt;

  constructor(
    private qv2: QuantsysV2Client,
    private memoryClient: OsMemoryStore,
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: RegimeDailyParams): ValidationResult {
    // 无参数，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(_args: RegimeDailyParams, _context: ToolContext): Promise<RegimeDailyResult> {
    const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

    // 幂等检查：今日已落库则跳过
    const existing = await this.memoryClient.searchMemory({ q: `regime ${today}`, scope: 'market:regime', limit: 3 });
    const dup = (existing?.items || []).find((it: any) => it.payload?.date === today && it.status !== 'deprecated');
    if (dup) {
      return { date: today, regime: dup.payload?.regime, evidence: dup.payload?.evidence, skipped: true };
    }

    const s: any = await this.qv2.getMarketSentiment();
    const fg = Number(s?.fearGreedIndex ?? 50);
    const adRatio = Number(s?.indicators?.advanceDecline?.ratio ?? 1);
    const volRatio = Number(s?.indicators?.volume?.volumeRatio ?? 1);

    // 数据质量防线
    const degraded = s?.degraded === true;
    const adSampleSize = Number(s?.indicators?.advanceDecline?.upCount ?? 0) + Number(s?.indicators?.advanceDecline?.downCount ?? 0);
    const avgRet5d = Number(s?.indicators?.indexPerformance?.avgReturn5DPct ?? 0);
    const nhSignal = s?.indicators?.newHighLow?.signal ?? 'neutral';
    const conflicts: string[] = [];

    if (fg >= 80 && (nhSignal === 'neutral' || avgRet5d < 0)) {
      conflicts.push(`fg=${fg} 极端贪婪但新高新低=${nhSignal}、指数5日收益=${avgRet5d}%——指标矛盾`);
    }
    if (fg <= 20 && nhSignal === 'neutral' && avgRet5d > 0) {
      conflicts.push(`fg=${fg} 极端恐慌但新高新低中性、指数5日收益为正——指标矛盾`);
    }
    if (adSampleSize > 0 && adSampleSize < 1000) {
      conflicts.push(`涨跌家数样本仅 ${adSampleSize} 只（全市场 5000+），广度指标非全市场口径`);
    }

    // regime 分类
    let regime = 'sideways';
    let reason = '情绪中性区间震荡';

    if (fg <= 20) {
      regime = 'panic';
      reason = `恐慌贪婪指数 ${fg} ≤ 20，恐慌市`;
    } else if (fg <= 35 && adRatio <= 0.5 && volRatio >= 1.5) {
      regime = 'panic';
      reason = `放量弱市恐慌：fg ${fg} 恐惧 + 涨跌比 ${adRatio}≤0.5 + 量能比 ${volRatio}≥1.5（放量下跌）`;
    } else if (fg >= 80) {
      regime = 'euphoria';
      reason = `恐慌贪婪指数 ${fg} ≥ 80，狂热市`;
    } else if (adRatio >= 1.5 && volRatio >= 1.2) {
      regime = 'risk_on';
      reason = `涨跌比 ${adRatio}≥1.5 且量能比 ${volRatio}≥1.2，偏多`;
    } else if (adRatio <= 0.67 && volRatio <= 0.9) {
      regime = 'risk_off';
      reason = `涨跌比 ${adRatio}≤0.67 且量能比 ${volRatio}≤0.9，偏空缩量`;
    }

    if ((regime === 'panic' || regime === 'euphoria') && (degraded || conflicts.length > 0)) {
      reason += `（⚠️ 数据降级/指标矛盾，极端判定可信度低）`;
    }

    const evidence = {
      fearGreedIndex: fg,
      advanceDeclineRatio: adRatio,
      volumeRatio: volRatio,
      sentimentScore: s?.sentimentScore,
      sentimentLevel: s?.sentimentLevel,
      reason,
      data_quality: degraded ? 'degraded' : 'ok',
      conflicts: conflicts.length > 0 ? conflicts : null,
      data_gap: '指数K线趋势维度缺失（M0 待补），当前仅情绪+量能维度',
    };

    // 落库 regime
      await this.memoryClient.createMemory({
      kind: 'episode',
      scope: 'market:regime',
      title: `regime ${today}: ${regime}`,
      content: `${today} 市场 regime = ${regime}（${reason}）。恐慌贪婪=${fg}，涨跌比=${adRatio}，量能比=${volRatio}。`,
      payload: { date: today, regime, evidence },
      status: 'testing',
      confidence: degraded || conflicts.length > 0 ? 0.35 : 0.7,
      source: 'regime_daily',
      provenance: { channel: 'dsh', session_kind: 'agent' },
    });

    // 情绪时间序列同步落库
    const dupSent = (await this.memoryClient.searchMemory({ q: `sentiment ${today}`, scope: 'market:sentiment', limit: 3 }))
      ?.items?.find((it: any) => it.payload?.date === today && it.status !== 'deprecated');

    if (!dupSent) {
      await this.memoryClient.createMemory({
        kind: 'episode',
        scope: 'market:sentiment',
        title: `sentiment ${today}: fg=${fg}`,
        content: `${today} 情绪序列：恐慌贪婪=${fg}，涨跌家数比=${adRatio}，量能比=${volRatio}，情绪分=${s?.sentimentScore}（${s?.sentimentLevel}）。`,
        payload: { date: today, fearGreedIndex: fg, advanceDeclineRatio: adRatio, volumeRatio: volRatio, raw: s?.indicators ?? null },
        status: 'testing',
        confidence: 0.7,
        source: 'regime_daily',
        provenance: { channel: 'dsh', session_kind: 'agent' },
      });
    }

    return { date: today, regime, evidence, skipped: false };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: RegimeDailyResult, _context: ToolContext): ToolResponse<RegimeDailyResult> {
    return {
      success: true,
      data: result,
    };
  }
}
