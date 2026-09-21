import type { ToolPrompt } from '@pi-investment/core-tool';

export interface LhbParams {
  /** 查询某日龙虎榜榜单（YYYY-MM-DD），与 symbol 二选一 */
  date?: string;
  /** 查个股龙虎榜上榜明细（6位代码），与 date 二选一 */
  symbol?: string;
}

export interface LhbResult {
  mode: string;
  available: boolean;
  records?: Array<Record<string, any>>;
  summary?: string;
  degraded_sources?: string[];
  note?: string;
  [key: string]: any;
}

export const lhbPrompt: ToolPrompt<LhbParams, LhbResult> = {
  description: '龙虎榜查询（游资/机构席位动向）。date 模式查某日全市场上榜记录（游资炒作标的+机构买卖席位）；symbol 模式查个股上榜明细。适用于：追踪游资动向、识别机构进出、博弈对手行为分析。解读参考：知名游资席位买入=短线情绪标的；机构席位大额卖出=出货预警。数据源为 akshare，盘中/非交易日可能无数据。⚠️ 降级协作：源失效时 Agent 可用 web_search 搜"龙虎榜 {日期}"或"{股票名} 龙虎榜"获取上榜信息。',

  useCases: ['游资动向追踪', '机构席位进出', '短线情绪标的识别'],

  parameters: {
    date: {
      type: 'string',
      description: '查某日龙虎榜（YYYY-MM-DD），须为交易日',
      example: '2026-08-29',
    },
    symbol: {
      type: 'string',
      description: '查个股上榜明细（6位代码）',
      example: '002241',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        mode: { type: 'string' },
        available: { type: 'boolean' },
        records: { type: 'array' },
        summary: { type: 'string' },
        degraded_sources: { type: 'array' },
        note: { type: 'string' },
      },
    },
    render: (args, data) => {
      const lines: string[] = [`## 龙虎榜（${data.mode}）`];
      if (!data.available) {
        lines.push(`⚠️ ${data.note || '数据源暂不可用'}`);
        return [{ type: 'text', text: lines.join('\n') }];
      }
      if (data.summary) lines.push('', data.summary);
      for (const r of (data.records || []).slice(0, 15)) {
        const name = r['名称'] || r['stock_name'] || '';
        const code = r['代码'] || r['symbol'] || '';
        const reason = r['上榜原因'] || r['reason'] || '';
        const net = r['净买入'] ?? r['net_buy'] ?? '';
        lines.push(`- ${code} ${name} ${reason} ${net !== '' ? `净买入${net}` : ''}`);
      }
      return [{ type: 'text', text: lines.join('\n') }];
    },
  },
};
