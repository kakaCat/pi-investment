/**
 * OpportunityScanTool - 机会扫描工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface OpportunityScanParams {
  scan_type?: 'technical' | 'fundamental' | 'hybrid' | 'accumulation';
  pool_id?: number;
  symbols?: string[];
  min_score?: number;
}

export interface OpportunityScanResult {
  opportunities: Array<{
    symbol: string;
    name: string;
    score: number;
    reasons: string[];
    signals: Record<string, any>;
    technical_score?: number;
    fundamental_score?: number;
    capital_score?: number;
    score_breakdown?: Record<string, any>;
    data_as_of?: string;
    validated_combo?: boolean;
    scoring_method?: string;
  }>;
  scan_summary: {
    total_scanned: number;
    opportunities_found: number;
    scan_time: string;
  };
}

export const opportunityScanPrompt: ToolPrompt<OpportunityScanParams, OpportunityScanResult> = {
  description: '扫描市场机会，识别潜在买入或卖出信号',
  useCases: [
    '盘前扫描今日机会',
    '发现超跌反弹标的',
    '识别突破形态',
    '寻找基本面改善股票',
  ],
  parameters: {
    scan_type: {
      type: 'string',
      description: '扫描类型：technical/fundamental/hybrid/accumulation(蓄势，找未启动标的)',
      example: 'hybrid',
    },
    pool_id: {
      type: 'number',
      description: '扫描指定股票池',
      example: 1,
    },
    symbols: {
      type: 'array',
      description: '扫描指定股票列表',
      example: ['000001', '600519'],
    },
    min_score: {
      type: 'number',
      description: '最低得分阈值',
      example: 70,
    },
  },
  examples: [
    'opportunity_scan({ scan_type: "hybrid" }) // 综合扫描市场机会',
    'opportunity_scan({ pool_id: 1, min_score: 80 }) // 扫描股票池1中高分机会',
    'opportunity_scan({ symbols: ["000001", "600519"], scan_type: "technical" }) // 扫描指定股票的技术形态',
  ],

  notes: [
    '💡 hybrid 模式综合技术+基本面，适合日常使用',
    '💡 technical 模式关注形态、突破、超跌反弹',
    '💡 fundamental 模式关注估值、业绩、财务质量',
    '💡 accumulation 模式（2026-11-10 上线）：蓄势扫描——找"波动压缩+缩量+趴着+资金温和流入"的未启动标的，与 momentum 哲学相反；特征阈值经全市场事件研究验证（5/10/20日超额 t=2.7~3.5 显著为正），命中 validated_combo 的优先级最高；蓄势≠立即买入，是观察仓候选',
    '⚠️ technical/hybrid/fundamental 模式实测偏右侧（追涨组全市场回测 5-10 日显著为负），找早期机会用 accumulation',
    'min_score 建议设置 70-80 以过滤低质量信号',
  ],

  relatedTools: ['screening', 'pool_filter'],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        opportunities: { type: 'array', description: '机会列表' },
        scan_summary: { type: 'object', additionalProperties: true, description: '扫描摘要' },
      },
    },
    render: (_args, data) => {
      // P1 透明度（2026-11-10，w-191eb58c）：透出四维明细 + 数据时点水印。
      // 技术面指标基于日K收盘，盘中扫描时 data_as_of 通常是昨日（T-1），必须显式告知。
      const asOfDates = [...new Set(
        data.opportunities.map(o => o.data_as_of).filter(Boolean)
      )] as string[];
      const asOf = asOfDates.length ? asOfDates.sort().reverse()[0] : null;
      const today = new Date().toISOString().slice(0, 10);
      const staleWarn = asOf && asOf < today
        ? ` ⚠️ 技术指标基于 ${asOf} 收盘（T-1 滞后，非盘中实时）`
        : '';
      return [
        { type: 'text', text: `🔍 机会扫描完成${staleWarn}` },
        { type: 'text', text: `` },
        { type: 'text', text: `📊 扫描范围: ${data.scan_summary.total_scanned} 只股票` },
        { type: 'text', text: `✨ 发现机会: ${data.scan_summary.opportunities_found} 个` },
        ...(asOf ? [{ type: 'text' as const, text: `🕐 指标数据截至: ${asOf}` }] : []),
        { type: 'text', text: `` },
        ...data.opportunities.slice(0, 5).map(opp => {
          const dims = (opp.technical_score !== undefined)
            ? ` [技术${opp.technical_score}/基本面${opp.fundamental_score}/资金${opp.capital_score}]`
            : '';
          const techDetail = opp.score_breakdown?.technical?.details
            ? ` 技术明细: ${Object.entries(opp.score_breakdown.technical.details)
                .filter(([, v]) => typeof v === 'number' && v !== 0)
                .map(([k, v]) => `${k}${(v as number) > 0 ? '+' : ''}${Number(v).toFixed(1)}`)
                .join(' ')}`
            : '';
          const combo = opp.validated_combo === true ? ' ✅命中验证组合' : '';
          return {
            type: 'text' as const,
            text: `• ${opp.symbol} ${opp.name} (得分: ${opp.score})${combo}${dims} - ${opp.reasons.join(', ')}${techDetail}`,
          };
        }),
      ];
    },
  },
};
