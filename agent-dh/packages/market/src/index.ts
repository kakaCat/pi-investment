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
      timeoutMs: 60000,  // 情绪接口偶发慢调用，放宽（mainline_scan 同款问题）
      execute: async () => {
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        // 幂等检查：今日已落库则跳过
        const existing = await qv2.searchMemory({ q: `regime ${today}`, scope: 'market:regime', limit: 3 });
        const dup = (existing?.items || []).find((it: any) => it.payload?.date === today && it.status !== 'deprecated');  // 已弃用记录不算重复
        if (dup) {
          return { date: today, regime: dup.payload?.regime, evidence: dup.payload?.evidence, skipped: true } as any;
        }

        const s: any = await qv2.getMarketSentiment();
        const fg = Number(s?.fearGreedIndex ?? 50);
        const adRatio = Number(s?.indicators?.advanceDecline?.ratio ?? 1);
        const volRatio = Number(s?.indicators?.volume?.volumeRatio ?? 1);

        // 2026-08-21 数据质量防线（review 专项）：
        // ①后端 degraded 标记直通；②指标内部矛盾检测——fg 极端但新高新低中性/
        //   指数 5 日收益为负 → 标记冲突、降置信；③涨跌家数样本过小（<1000 只，
        //   全市场 5000+）说明是非全市场样本，广度指标可信度降权
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

        // regime 分类（情绪维度；趋势维度待 M0 指数K线）
        // 数据降级或有矛盾时，极端判定降级为方向性判定并显著降置信
        let regime = 'sideways';
        let reason = '情绪中性区间震荡';
        if (fg <= 20) { regime = 'panic'; reason = `恐慌贪婪指数 ${fg} ≤ 20，恐慌市`; }
        else if (fg >= 80) { regime = 'euphoria'; reason = `恐慌贪婪指数 ${fg} ≥ 80，狂热市`; }
        else if (adRatio >= 1.5 && volRatio >= 1.2) { regime = 'risk_on'; reason = `涨跌比 ${adRatio}≥1.5 且量能比 ${volRatio}≥1.2，偏多`; }
        else if (adRatio <= 0.67 && volRatio <= 0.9) { regime = 'risk_off'; reason = `涨跌比 ${adRatio}≤0.67 且量能比 ${volRatio}≤0.9，偏空缩量`; }
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

        await qv2.createMemory({
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

        // M1-3 情绪时间序列同步落库（同一数据源，一条记录）
        const dupSent = (await qv2.searchMemory({ q: `sentiment ${today}`, scope: 'market:sentiment', limit: 3 }))
          ?.items?.find((it: any) => it.payload?.date === today && it.status !== 'deprecated');  // 已弃用记录不算重复
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
      timeoutMs: 90000,  // 板块接口冷启动 15s+（2026-08-22 实测两次 30s 超时），放宽到 90s
      execute: async (args: any) => {
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        const existing = await qv2.searchMemory({ q: `mainline ${today}`, scope: 'market:mainline', limit: 3 });
        const dup = (existing?.items || []).find((it: any) => it.payload?.date === today && it.status !== 'deprecated');  // 已弃用记录不算重复
        if (dup) {
          return { date: today, mainlines: dup.payload?.mainlines, skipped: true } as any;
        }

        const res: any = await qv2.getSectorAnalysis({ days: args.days ?? 5, limit: 10 });
        // 响应结构宽容解析：取板块数组（名称+涨跌幅+资金流）
        // 2026-08-21 实测：后端返回中文字段（板块名称/涨跌幅/总市值/类型），
        // 无资金流字段；undefined 字段会触发工具输出 not lossless JSON，一律 ?? null
        const sectors: any[] = res?.sectors || res?.items || res?.ranking || [];
        const top3 = sectors.slice(0, 3).map((sec: any, i: number) => ({
          rank: i + 1,
          sector: sec['板块名称'] ?? sec.name ?? sec.sector ?? sec.industry ?? `未知板块${i + 1}`,
          code: sec['板块代码'] ?? sec.code ?? null,
          change_pct: sec['涨跌幅'] ?? sec.change_pct ?? sec.changePct ?? sec.pct ?? null,
          market_cap: sec['总市值'] ?? null,
          type: sec['类型'] ?? null,
          basis: `近${args.days ?? 5}日板块强度排名前${i + 1}（按板块涨跌幅）`,
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

    // M2-1: 主线→标的映射器（RFC 004/005，2026-08-22）
    ctx.tools.register(defineTool({
      name: 'mainline_stocks',
      description: '主线→标的映射：输入主线名称（如"白银"，或不传则读当日落库主线 Top3 全量映射），输出每条主线的候选标的（成分股按市值排序取龙头）+ 入选理由 + 风险标注（ST/亏损/高估值/操纵未检测提示）。供：盘后主线跟进、盘前候选池构建。买入前仍需过 manipulation_detect 与 R-001 确认流程。',
      parameters: {
        mainline: {
          type: 'string',
          description: '主线名称（如"白银"）。不传则读取最新落库的市场主线 Top3 全部映射',
        },
        top_n: { type: 'integer', description: '每条主线取前 N 只候选，默认 3', default: 3 },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            date: { type: 'string' },
            mappings: {
              type: 'array',
              items: { type: 'object', additionalProperties: true },
            },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        const topN = args.top_n ?? 3;
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        // 1. 确定主线列表
        let mainlines: string[] = [];
        if (args.mainline) {
          mainlines = [args.mainline];
        } else {
          const res = await qv2.searchMemory({ q: 'mainline', scope: 'market:mainline', limit: 5 });
          const latest = (res?.items || [])
            .filter((it: any) => it.status !== 'deprecated' && it.payload?.date)
            .sort((a: any, b: any) => String(b.payload.date).localeCompare(String(a.payload.date)))[0];
          mainlines = (latest?.payload?.mainlines || []).map((m: any) => m.sector).filter(Boolean);
          if (mainlines.length === 0) throw new Error('未找到落库的市场主线（先运行 mainline_scan）');
        }

        // 2. 逐主线取成分股并排序（市值龙头优先），附入选理由与风险标注
        const mappings = [];
        for (const ml of mainlines) {
          let stocks: any[] = [];
          let sectorCode: string | null = null;
          try {
            const res: any = await qv2.getSectorStocks(ml);
            sectorCode = res?.sectorCode ?? null;
            stocks = res?.stocks || [];
          } catch (e: any) {
            mappings.push({ mainline: ml, candidates: [], error: `成分股获取失败: ${e?.message}` });
            continue;
          }

          const sorted = [...stocks].sort((a, b) => Number(b.marketCapBillion ?? 0) - Number(a.marketCapBillion ?? 0));
          const candidates = sorted.slice(0, topN).map((s: any, i: number) => {
            const risks: string[] = [];
            const name = String(s.name ?? '');
            if (/ST/i.test(name)) risks.push('ST/退市风险标的');
            const pe = Number(s.pe);
            if (!(pe > 0)) risks.push('PE 缺失或亏损（盈利不确定）');
            else if (pe > 100) risks.push(`高估值（PE ${pe}）`);
            risks.push('操纵嫌疑未检测（买入前需过 manipulation_detect）');

            return {
              rank_in_sector: i + 1,
              symbol: s.symbol ?? null,
              name: s.name ?? null,
              pe: s.pe ?? null,
              market_cap_billion: s.marketCapBillion ?? null,
              reason: `${ml}板块成分股，市值第${i + 1}（${s.marketCapBillion ?? '?'} 亿），主线龙头候选`,
              risks,
            };
          });

          mappings.push({ mainline: ml, sector_code: sectorCode, candidates });
        }

        // 3. 落库（scope=market:watchlist，供盘前/复盘检索；同日同主线幂等跳过由调用方控制——此处总是记录最新一次映射）
        await qv2.createMemory({
          kind: 'episode',
          scope: 'market:watchlist',
          title: `mainline_stocks ${today}: ${mainlines.join('/')}`,
          content: `${today} 主线映射：${mappings.map(m => `${m.mainline}→[${(m.candidates || []).map((c: any) => c.name).join(',')}]`).join('；')}`,
          payload: { date: today, mappings },
          status: 'testing',
          confidence: 0.6,
          source: 'mainline_stocks',
          provenance: { channel: 'dsh', session_kind: 'agent' },
        });

        return { date: today, mappings } as any;
      },
    } as any));
  }
}
