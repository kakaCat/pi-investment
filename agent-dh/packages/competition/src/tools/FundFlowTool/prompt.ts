import type { ToolPrompt } from '@pi-investment/core-tool';

export interface FundFlowParams {
  /** 股票代码。传入=查该股主力资金流+两融；不传=查板块资金流全景 */
  symbol?: string;
  /** 回溯天数（个股模式，默认 5） */
  days?: number;
}

export interface FundFlowResult {
  mode: string;
  available: boolean;
  fund_flow?: Array<Record<string, any>>;
  margin?: Array<Record<string, any>>;
  sector_flow?: Array<Record<string, any>>;
  summary?: string;
  degraded_sources?: string[];
  note?: string;
  [key: string]: any;
}

export const fundFlowPrompt: ToolPrompt<FundFlowParams, FundFlowResult> = {
  description: '资金动向一站式查询：传 symbol 查该股主力资金流（主力/大单净流入）+ 融资融券杠杆资金；不传 symbol 查板块资金流全景。适用于：判断主力进出、识别板块资金轮动、评估杠杆情绪。博弈维度——主力持续流入+两融放大=机构/杠杆资金共识。数据源为 akshare，可能临时不可用（degraded_sources 会标注），失败时结合其他维度决策。',

  useCases: ['主力资金进出判断', '板块资金轮动', '两融杠杆情绪评估'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位股票代码，如 600519。传入=个股资金流+两融；不传=板块资金流全景',
      example: '002241',
    },
    days: {
      type: 'number',
      description: '回溯天数（个股模式，1-30，默认 5）',
      example: 5,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        mode: { type: 'string' },
        available: { type: 'boolean' },
        fund_flow: { type: 'array' },
        margin: { type: 'array' },
        sector_flow: { type: 'array' },
        summary: { type: 'string' },
        degraded_sources: { type: 'array' },
        note: { type: 'string' },
      },
    },
    render: (args, data) => {
      const lines: string[] = [`## 资金动向（${data.mode}）`];
      if (!data.available) {
        lines.push(`⚠️ 数据源暂不可用：${data.note || '未知原因'}`);
        if (data.degraded_sources?.length) lines.push(`降级源：${data.degraded_sources.join(', ')}`);
        return [{ type: 'text', text: lines.join('\n') }];
      }
      if (data.summary) lines.push('', data.summary);
      if (data.fund_flow?.length) {
        lines.push('', '### 主力资金流（近几日）');
        for (const r of data.fund_flow.slice(0, 5)) {
          lines.push(`- ${r.date} 主力净流入 ${r.mainNetInflow ?? '?'}万 (${r.mainNetInflowRate ?? '?'}%)`);
        }
      }
      if (data.margin?.length) {
        lines.push('', '### 融资融券');
        for (const r of data.margin.slice(0, 3)) {
          lines.push(`- ${r.date} 两融余额 ${r.totalBalance ?? '?'}万，融资买入 ${r.financingBuy ?? '?'}万`);
        }
      }
      if (data.sector_flow?.length) {
        lines.push('', '### 板块资金流 TOP');
        for (const r of data.sector_flow.slice(0, 10)) {
          lines.push(`- ${r['行业'] || r['名称'] || JSON.stringify(r).slice(0, 60)}`);
        }
      }
      if (data.degraded_sources?.length) lines.push('', `> ⚠️ 部分源降级：${data.degraded_sources.join(', ')}`);
      return [{ type: 'text', text: lines.join('\n') }];
    },
  },
};
