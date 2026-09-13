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
   * v2 词表 → 本侧词表（唯一映射点）。
   *
   * 2026-09-13（w-a9ec14d7）：两套词表此前各自演化、互不知情：
   *  · v2 quant.market_regime（regime_daily 任务）：range / trend_up / trend_down / panic / euphoria
   *  · 本工具自算：sideways / risk_on / risk_off / panic / euphoria
   * 下游 regime_position_limit 的仓位映射表只认后一套 → v2 说 range 时它按"未知"兜底，
   * 而本地自算说 risk_off 时它按 40% 算 —— 同一个概念两个答案。
   */
  private static readonly V2_REGIME_MAP: Record<string, string> = {
    range: 'sideways',
    trend_up: 'risk_on',
    trend_down: 'risk_off',
    panic: 'panic',
    euphoria: 'euphoria',
  };

  /**
   * 取 **规范源**：v2 的 quant.market_regime（由 market_perception_daily 15:30 落库）。
   * 端点：GET /api/market/perception/regime?days=1（与其它工具直连 v2 端点的既有做法一致）。
   * 任何失败都返回 null，由调用方决定是退回本地计算还是放弃 —— 不抛、也不静默冒充成功。
   */
  private async fetchCanonicalRegime(): Promise<any | null> {
    try {
      const base = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const res = await fetch(base + '/api/market/perception/regime?days=1');
      if (!res.ok) return null;
      const body: any = await res.json();
      const row = (body?.data || [])[0];
      if (!row?.regime || !row?.trade_date) return null;
      return row;
    } catch {
      return null;
    }
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

    // ── 单一事实源：先读 v2 的规范 regime（2026-09-13 w-a9ec14d7）────────────────
    // 实测 2026-09-11 两源同日给出不同答案：v2 quant.market_regime = range（无降级），
    // 本地自算写进 memory 的 market:regime = risk_off + degraded，而 regime_position_limit 读的是后者。
    // 现改为：v2 为唯一事实源，本工具做**镜像**（词表显式映射）；
    // 仅当 v2 不可达才退回本地计算，并显式标注 source=local_fallback + data_quality=degraded
    // —— 退化必须可见，不能让下游把兜底值当成规范值。
    const canonical = await this.fetchCanonicalRegime();
    const canonicalDate = canonical ? String(canonical.trade_date).slice(0, 10) : today;
    const mapped = canonical ? (RegimeDailyTool.V2_REGIME_MAP[String(canonical.regime)] ?? 'sideways') : null;

    // 幂等检查：同一天（规范源口径）已落库则跳过
    const existing = await this.memoryClient.searchMemory({ q: `regime ${canonicalDate}`, scope: 'market:regime', limit: 3 });
    const dup = (existing?.items || []).find((it: any) => it.payload?.date === canonicalDate && it.status !== 'deprecated');
    if (dup) {
      return { date: canonicalDate, regime: dup.payload?.regime, evidence: dup.payload?.evidence, skipped: true };
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

    // regime 分类（本地口径；仅当规范源不可用时才真正被采用）
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

    // 本地口径的 evidence（作为兜底与对照留档，无论是否采用都保留，便于日后核对两套判定的差异）
    const localEvidence = {
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

    // 最终落库口径
    let finalDate = canonicalDate;
    let finalRegime: string;
    let evidence: any;
    if (canonical && mapped) {
      // 规范源可用：以它为准（镜像）
      finalRegime = mapped;
      evidence = {
        source: 'v2:market_regime',
        canonical: true,
        v2_regime: String(canonical.regime),
        v2_trade_date: canonicalDate,
        v2_reason: canonical.reason ?? null,
        v2_indicators: {
          index_trend_score: canonical.index_trend_score,
          sentiment_score: canonical.sentiment_score,
          volume_ratio: canonical.volume_ratio,
          ad_ratio: canonical.ad_ratio,
        },
        reason: `镜像 v2 规范 regime ${canonical.regime} → ${mapped}（${canonical.reason ?? ''}）`,
        data_quality: 'ok',
        conflicts: null,
        local_evidence: localEvidence,
        note: '本工具自 2026-09-13 起不再自算 regime，只镜像 v2 quant.market_regime（唯一事实源）',
      };
    } else {
      // 规范源不可达：退回本地计算，但**必须标为降级**（下游据此收紧仓位，而不是当成规范值）
      finalRegime = regime;
      evidence = {
        ...localEvidence,
        source: 'local_fallback',
        canonical: false,
        data_quality: 'degraded',
        conflicts: [
          ...(conflicts || []),
          'v2 quant.market_regime 不可达（/api/market/perception/regime 取不到），本值系本地兜底计算，非规范值',
        ],
        note: 'v2 规范源不可达时的本地兜底；恢复后应重新拉取覆盖',
      };
    }

    // 落库 regime
      await this.memoryClient.createMemory({
      kind: 'episode',
      scope: 'market:regime',
      title: `regime ${finalDate}: ${finalRegime}`,
      content: `${finalDate} 市场 regime = ${finalRegime}（${evidence.reason}）。恐慌贪婪=${fg}，涨跌比=${adRatio}，量能比=${volRatio}。`,
      payload: { date: finalDate, regime: finalRegime, evidence },
      status: 'testing',
      confidence: (!canonical || degraded || (conflicts || []).length > 0) ? 0.35 : 0.7,
      source: canonical ? 'regime_daily(v2-mirror)' : 'regime_daily(local-fallback)',
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

    return { date: finalDate, regime: finalRegime, evidence, skipped: false } as any;
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