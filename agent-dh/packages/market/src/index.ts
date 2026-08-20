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
 * Market Analysis Plugin for Agent-DH
 *
 * Market style detection, sector analysis, chip distribution analysis.
 */
export default class MarketPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'market');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 市场风格检测
    ctx.tools.register(defineTool({
      name: 'market_style_detect',
      description: '检测当前市场主导风格（价值/成长/周期）及置信度，返回各风格得分、观测指标和推荐因子。适用于：定期（如每周）判断市场偏好、指导配置方向——风格偏价值时增配低估值蓝筹，偏成长时关注科技成长。行业层面的细节分析用 sector_analysis。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            style: { type: 'string', description: '主导风格：value（价值）/growth（成长）/cycle（周期）' },
            confidence: { type: 'number', description: '置信度（0-1）' },
            scores: { type: 'object', additionalProperties: true, description: '各风格得分，如 {value, growth, cycle}' },
            indicators: { type: 'object', additionalProperties: true, description: '观测指标（银行/科技/周期板块表现、成交量变化、波动率等）' },
            recommendedFactors: { type: 'array', description: '当前风格下的推荐因子，如 roe/momentum' },
            detectionDate: { type: 'string', description: '检测日期（YYYY-MM-DD）' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async () => {
        return qv2.getMarketStyle() as any;
      },
    } as any));

    // 行业分析
    ctx.tools.register(defineTool({
      name: 'sector_analysis',
      description: '分析行业板块表现、资金流向与轮动信号。适用于：发现强势板块、判断行业轮动节奏、选择配置方向。与 market_style_detect 的分工：后者看市场整体风格，本工具看行业细节。确认轮动方向后可用 rotation_proposal 生成调仓提案。',
      parameters: {
        sector: {
          type: 'string',
          description: '行业名称或代码，如 白酒、半导体、银行。传入则返回该行业详情；不传则返回全部行业排名',
        },
        days: {
          type: 'integer',
          description: '分析周期（交易日），默认 5。短线轮动看 5-10 天，中线趋势看 20-60 天',
          default: 5,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            sectors: { type: 'array', description: '行业列表，按涨幅排序' },
            top_performers: { type: 'array', description: '表现最好的行业' },
            worst_performers: { type: 'array', description: '表现最差的行业' },
            rotation_signal: { type: 'string', description: '轮动信号' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return qv2.getSectorAnalysis({
          sector: args.sector,
          days: args.days || 5,
        }) as any;
      },
    } as any));

    // 筹码分析
    ctx.tools.register(defineTool({
      name: 'chip_analysis',
      description: '分析个股筹码分布与成本结构：平均成本、获利盘比例、筹码集中度、支撑/压力位。适用于：判断支撑压力位、识别主力成本区、评估突破有效性。解读参考：获利盘比例过高（如>90%）说明浮盈兑现压力大，过低说明套牢盘沉重、反弹阻力大。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            avg_cost: { type: 'number', description: '平均成本（元）' },
            profit_ratio: { type: 'number', description: '获利盘比例（%）' },
            concentration: { type: 'number', description: '筹码集中度（%）' },
            support_levels: { type: 'array', description: '支撑位列表' },
            resistance_levels: { type: 'array', description: '压力位列表' },
            chip_distribution: { type: 'array', description: '筹码分布数据' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return qv2.getChipDistribution(args.symbol) as any;
      },
    } as any));

    // ===== M1 市场感知：每日落库三件套（RFC 004/005，2026-08-20）=====
    // 落库介质：memory（kind=episode, scope=market:*），不依赖后端改表；
    // 幂等：同日已有记录则跳过（盘后例程重复触发不会产生重复记录）

    // M1-1 + M1-3: regime 与情绪每日落库
    ctx.tools.register(defineTool({
      name: 'regime_daily',
      description: '计算并落库当日市场 regime（趋势/震荡/恐慌/狂热）与情绪时间序列。判定依据：恐慌贪婪指数 + 涨跌家数比 + 量能比（指数K线趋势维度待 M0 数据地基补齐后接入）。每日盘后例程调用一次，幂等（同日重复调用跳过）。供：M4 仓位映射、验证门裁决的 regime 对齐、复盘统计 regime 判定准确率。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            date: { type: 'string' },
            regime: { type: 'string', description: 'panic / euphoria / risk_on / risk_off / sideways' },
            evidence: { type: 'object', additionalProperties: true },
            skipped: { type: 'boolean', description: 'true=今日已落库，未重复写入' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 30000,
      execute: async () => {
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        // 幂等检查：今日已落库则跳过
        const existing = await qv2.searchMemory({ q: `regime ${today}`, scope: 'market:regime', limit: 3 });
        const dup = (existing?.items || []).find((it: any) => it.payload?.date === today);
        if (dup) {
          return { date: today, regime: dup.payload?.regime, evidence: dup.payload?.evidence, skipped: true } as any;
        }

        const s: any = await qv2.getMarketSentiment();
        const fg = Number(s?.fearGreedIndex ?? 50);
        const adRatio = Number(s?.indicators?.advanceDecline?.ratio ?? 1);
        const volRatio = Number(s?.indicators?.volume?.volumeRatio ?? 1);

        // regime 分类（情绪维度；趋势维度待 M0 指数K线）
        let regime = 'sideways';
        let reason = '情绪中性区间震荡';
        if (fg <= 20) { regime = 'panic'; reason = `恐慌贪婪指数 ${fg} ≤ 20，恐慌市`; }
        else if (fg >= 80) { regime = 'euphoria'; reason = `恐慌贪婪指数 ${fg} ≥ 80，狂热市`; }
        else if (adRatio >= 1.5 && volRatio >= 1.2) { regime = 'risk_on'; reason = `涨跌比 ${adRatio}≥1.5 且量能比 ${volRatio}≥1.2，偏多`; }
        else if (adRatio <= 0.67 && volRatio <= 0.9) { regime = 'risk_off'; reason = `涨跌比 ${adRatio}≤0.67 且量能比 ${volRatio}≤0.9，偏空缩量`; }

        const evidence = {
          fearGreedIndex: fg,
          advanceDeclineRatio: adRatio,
          volumeRatio: volRatio,
          sentimentScore: s?.sentimentScore,
          sentimentLevel: s?.sentimentLevel,
          reason,
          data_gap: '指数K线趋势维度缺失（M0 待补），当前仅情绪+量能维度',
        };

        await qv2.createMemory({
          kind: 'episode',
          scope: 'market:regime',
          title: `regime ${today}: ${regime}`,
          content: `${today} 市场 regime = ${regime}（${reason}）。恐慌贪婪=${fg}，涨跌比=${adRatio}，量能比=${volRatio}。`,
          payload: { date: today, regime, evidence },
          status: 'testing',
          confidence: 0.7,
          source: 'regime_daily',
          provenance: { channel: 'dsh', session_kind: 'agent' },
        });

        // M1-3 情绪时间序列同步落库（同一数据源，一条记录）
        const dupSent = (await qv2.searchMemory({ q: `sentiment ${today}`, scope: 'market:sentiment', limit: 3 }))
          ?.items?.find((it: any) => it.payload?.date === today);
        if (!dupSent) {
          await qv2.createMemory({
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

        return { date: today, regime, evidence, skipped: false } as any;
      },
    } as any));

    // M1-2: 每日主线识别（Top3 强势主线 + 依据）
    ctx.tools.register(defineTool({
      name: 'mainline_scan',
      description: '识别当日市场主线 Top3（强势板块聚类：涨幅+资金流向），落库时间序列（scope=market:mainline）。催化剂关联（政策/事件）由盘后例程的 LLM 结合 web_search 补充。幂等：同日重复调用跳过。供：主线→标的映射（M2-1）、每日复盘主线一致率统计。',
      parameters: {
        days: { type: 'integer', description: '板块表现统计窗口（交易日），默认 5', default: 5 },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            date: { type: 'string' },
            mainlines: { type: 'array', items: { type: 'object', additionalProperties: true } },
            skipped: { type: 'boolean' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        const existing = await qv2.searchMemory({ q: `mainline ${today}`, scope: 'market:mainline', limit: 3 });
        const dup = (existing?.items || []).find((it: any) => it.payload?.date === today);
        if (dup) {
          return { date: today, mainlines: dup.payload?.mainlines, skipped: true } as any;
        }

        const res: any = await qv2.getSectorAnalysis({ days: args.days ?? 5, limit: 10 });
        // 响应结构宽容解析：取板块数组（名称+涨跌幅+资金流）
        const sectors: any[] = res?.sectors || res?.items || res?.ranking || [];
        const top3 = sectors.slice(0, 3).map((sec: any, i: number) => ({
          rank: i + 1,
          sector: sec.name ?? sec.sector ?? sec.industry,
          change_pct: sec.change_pct ?? sec.changePct ?? sec.pct ?? null,
          fund_flow: sec.fund_flow ?? sec.fundFlow ?? sec.net_inflow ?? null,
          basis: `近${args.days ?? 5}日板块强度排名前${i + 1}${sec.fund_flow != null || sec.net_inflow != null ? '，资金净流入' : ''}`,
        }));

        await qv2.createMemory({
          kind: 'episode',
          scope: 'market:mainline',
          title: `mainline ${today}: ${top3.map(t => t.sector).join('/')}`,
          content: `${today} 主线 Top3：${top3.map(t => `${t.rank}.${t.sector}(${t.change_pct ?? '?'}%)`).join('，')}。催化剂关联待盘后例程补充。`,
          payload: { date: today, mainlines: top3, catalyst: null, note: '催化剂由盘后例程 LLM 结合 web_search 补充' },
          status: 'testing',
          confidence: 0.6,
          source: 'mainline_scan',
          provenance: { channel: 'dsh', session_kind: 'agent' },
        });

        return { date: today, mainlines: top3, skipped: false } as any;
      },
    } as any));
  }
}
