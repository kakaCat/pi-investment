import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Competition Intelligence Plugin for Agent-DH
 *
 * Market competition analysis: opponent behavior, battlefield assessment, manipulation detection.
 */
export default class CompetitionPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'competition');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 1. 对手行为分析
    ctx.tools.register(defineTool({
      name: 'opponent_behavior',
      description: '分析市场参与者（散户/机构/游资）的行为与情绪，识别对手错误和博弈机会。适用于：判断当前谁在主导市场、散户是否恐慌（错杀机会）、机构是否出货（撤退信号）、游资是否撤退（炒作结束）。返回机会信号与风险警告列表，是博弈决策的核心输入。',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，如 600519。传入则分析该股的参与者结构；不传则分析全市场总体格局',
        },
        focus: {
          type: 'string',
          description: '分析重点。retail：散户情绪（panic 恐慌=潜在买点，fomo 狂热=潜在卖点）；institution：机构动向（建仓/出货）；hot_money：游资活跃度（拉高/撤退）；all（默认）：三方综合分析',
          enum: ['retail', 'institution', 'hot_money', 'all'],
          default: 'all',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码或 market' },
            retail_sentiment: { type: 'string', description: '散户情绪：panic/fear/neutral/greed/fomo' },
            institution_flow: { type: 'string', description: '机构资金流向：heavy_inflow/inflow/neutral/outflow/heavy_outflow' },
            hot_money_activity: { type: 'string', description: '游资活跃度：high/medium/low' },
            opportunity_signals: { type: 'array', description: '博弈机会信号列表' },
            risk_warnings: { type: 'array', description: '风险警告列表' },
            analysis_summary: { type: 'string', description: '综合分析摘要' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        return qv2.getOpponentBehavior({
          symbol: args.symbol,
          focus: args.focus || 'all',
        }) as any;
      },
    } as any));

    // 2. 池子战场评估
    ctx.tools.register(defineTool({
      name: 'pool_battlefield',
      description: '评估指定股票池的博弈竞争优势：综合评分、对手分析、风险评估、操作建议及其在所有池中的排名。适用于：定期评估各池子优劣、决定把资金和注意力投向哪个战场。先用 pool_list 获取池子ID；池内个股的参与者细节用 opponent_behavior。',
      parameters: {
        pool_id: {
          type: 'integer',
          description: '股票池ID，通过 pool_list 获取',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            pool_id: { type: 'integer', description: '股票池ID' },
            pool_name: { type: 'string', description: '股票池名称' },
            competitive_score: { type: 'number', description: '竞争优势评分（0-100，越高越好）' },
            opponent_analysis: { type: 'object', description: '对手分析详情', additionalProperties: true },
            risk_assessment: { type: 'object', description: '风险评估详情', additionalProperties: true },
            recommendations: { type: 'array', description: '操作建议列表' },
            ranking: { type: 'integer', description: '在所有池子中的排名' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        return qv2.getPoolBattlefield({ pool_id: args.pool_id }) as any;
      },
    } as any));

    // 3. 操纵检测
    ctx.tools.register(defineTool({
      name: 'manipulation_detect',
      description: '检测个股操纵嫌疑（拉高出货、对倒交易、诱多诱空等），给出嫌疑评分、检测到的模式、证据列表和操作建议。适用于：买入陌生标的前排雷、识别操纵崩盘后的抄底机会。评分高（如>70）时应回避，或等待崩盘后的机会窗口。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        days: {
          type: 'integer',
          description: '分析最近 N 天的数据，默认 30。操纵周期较长时可加大到 60-90',
          default: 30,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            manipulation_score: { type: 'number', description: '操纵嫌疑评分（0-100，越高嫌疑越大）' },
            detected_patterns: { type: 'array', description: '检测到的操纵模式列表' },
            risk_level: { type: 'string', description: '风险等级：low（低风险）/medium（中风险）/high（高风险）' },
            recommendation: { type: 'string', description: '建议：avoid（回避）/watch（观望）/opportunity（操纵后机会）' },
            evidence: { type: 'array', description: '证据列表' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        // M2-2 重写（2026-08-22）：后端 /api/game/market/manipulation-detect 是
        // 全市场扫描（symbol 参数被忽略），契约与"个股排雷"不符且响应 30s+ 必超时。
        // 改为本地基于个股 K 线计算嫌疑评分（数据快、契约正确）。
        return detectManipulationLocal(qv2, args.symbol, args.days || 30);
      },
    } as any));
  }
}

/**
 * 个股操纵嫌疑评分（M2-2 本地实现）
 * 基于日 K 线的行为特征打分（0-100）：
 *  - 短期暴涨（20日涨幅>50%）+25
 *  - 连续涨停（>=9.9% 的日数≥3）+20
 *  - 极端振幅（单日振幅>15% 的日数≥2）+15
 *  - 异常放量（单日量/20日均量>5 的日数≥2）+15（对倒嫌疑）
 *  - 放量急跌（单日跌≤-7% 且量比>2）+15
 *  - 崩盘后企稳（20日跌>30% 且近5日振幅收敛）标记抄底机会
 */
async function detectManipulationLocal(qv2: QuantsysV2Client, symbol: string, days: number): Promise<any> {
  const end = new Date();
  const start = new Date(end.getTime() - Math.max(days, 30) * 2 * 86400000);  // 多取自然日补足交易日
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const klines: any[] = await qv2.getKlines(symbol, fmt(start), fmt(end), 'daily');
  if (!klines || klines.length < 10) {
    return { symbol, risk_level: 'unknown', recommendation: 'watch',
      detected_patterns: [], evidence: [`K线数据不足（${klines?.length ?? 0} 根），无法评估`] } as any;
  }

  const bars = klines.slice(-Math.max(days, 20));
  const last20 = klines.slice(-20);
  let score = 0;
  const patterns: string[] = [];
  const evidence: string[] = [];

  const pct = (a: number, b: number) => (b - a) / a * 100;
  const close0 = last20[0].close, closeN = last20[last20.length - 1].close;
  // 2026-08-22 验收修正：量比基线取"前 20 日"（形态出现前的平静期），
  // 原实现用 last20（含爆量日）会自我稀释基线导致漏报
  const prior20 = klines.slice(-40, -20);
  const baselineBars = prior20.length >= 10 ? prior20 : last20;
  const avgVol20 = baselineBars.reduce((s: number, k: any) => s + (k.volume || 0), 0) / baselineBars.length;

  // 1. 短期暴涨
  const chg20 = pct(close0, closeN);
  if (chg20 > 50) { score += 25; patterns.push('短期暴涨'); evidence.push(`近20日涨幅 ${chg20.toFixed(1)}% > 50%`); }

  // 2. 连续涨停
  let limitUps = 0;
  for (let i = 1; i < bars.length; i++) {
    if (pct(bars[i - 1].close, bars[i].close) >= 9.9) limitUps++;
  }
  if (limitUps >= 3) { score += 20; patterns.push('连续涨停'); evidence.push(`窗口内涨停 ${limitUps} 次（≥3）`); }

  // 3. 极端振幅
  let extremeAmp = 0;
  for (let i = 1; i < bars.length; i++) {
    const amp = (bars[i].high - bars[i].low) / bars[i - 1].close * 100;
    if (amp > 15) extremeAmp++;
  }
  if (extremeAmp >= 2) { score += 15; patterns.push('极端振幅'); evidence.push(`单日振幅>15% 出现 ${extremeAmp} 次`); }

  // 4. 异常放量（对倒嫌疑）
  let volSpikes = 0;
  for (const k of bars) {
    if (avgVol20 > 0 && (k.volume || 0) / avgVol20 > 5) volSpikes++;
  }
  if (volSpikes >= 2) { score += 15; patterns.push('异常放量'); evidence.push(`量比>5 的异常放量 ${volSpikes} 日（对倒嫌疑）`); }

  // 5. 放量急跌
  let dumpDays = 0;
  for (let i = 1; i < bars.length; i++) {
    const drop = pct(bars[i - 1].close, bars[i].close);
    const volRatio = avgVol20 > 0 ? (bars[i].volume || 0) / avgVol20 : 0;
    if (drop <= -7 && volRatio > 2) dumpDays++;
  }
  if (dumpDays >= 1) { score += 15; patterns.push('放量急跌'); evidence.push(`放量急跌（≤-7%且量比>2）${dumpDays} 日`); }

  // 6. 崩盘后企稳 → 抄底机会窗口
  let opportunity = false;
  const last5 = klines.slice(-5);
  if (chg20 < -30 && last5.length === 5) {
    const amp5 = (Math.max(...last5.map((k: any) => k.high)) - Math.min(...last5.map((k: any) => k.low))) / closeN * 100;
    if (amp5 < 10) {
      opportunity = true;
      patterns.push('崩盘后企稳');
      evidence.push(`20日跌幅 ${chg20.toFixed(1)}%，近5日振幅收敛至 ${amp5.toFixed(1)}%——操纵崩盘后的潜在机会窗口`);
    }
  }

  const risk = score > 70 ? 'high' : score >= 40 ? 'medium' : 'low';
  const recommendation = opportunity ? 'opportunity' : score > 70 ? 'avoid' : score >= 40 ? 'watch' : 'normal';

  return {
    symbol,
    manipulation_score: Math.min(100, score),
    risk_level: risk,
    recommendation,
    detected_patterns: patterns,
    evidence: evidence.length > 0 ? evidence : ['未发现显著操纵特征'],
    window_days: bars.length,
    note: '本地 K 线行为特征评分（M2-2）。后端全市场扫描接口契约错位（忽略个股参数）已报修基建线',
  } as any;
}
