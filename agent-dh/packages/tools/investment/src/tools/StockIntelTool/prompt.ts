import type { ToolPrompt } from '@pi-investment/core-tool';

export interface StockIntelParams {
  /** 股票代码（6位，必填） */
  symbol: string;
  /** 情报类型：announcements=公告，news=新闻，insider=内部人交易（高管增减持），all=全部（默认） */
  kind?: 'announcements' | 'news' | 'insider' | 'all';
}

export interface StockIntelResult {
  symbol: string;
  available: boolean;
  announcements?: Array<Record<string, any>>;
  news?: Array<Record<string, any>>;
  insider_trades?: Array<Record<string, any>>;
  summary?: string;
  degraded_sources?: string[];
  note?: string;
  [key: string]: any;
}

export const stockIntelPrompt: ToolPrompt<StockIntelParams, StockIntelResult> = {
  description: '个股情报聚合：公告+新闻+内部人交易（高管增减持）三源合一。适用于：买入前排雷（公告暴雷/高管减持=危险信号）、事件驱动分析（新闻催化）、内部人信心判断（高管增持=底部信号）。买入前建议作为 R-009 基本面维度的排雷输入。数据源为 akshare，部分源可能临时不可用（degraded_sources 标注），单源失败不影响其他源。⚠️ 降级协作：当 degraded_sources 非空（源失效）时，Agent 应主动用 web_search 补充该股的公告/新闻/增减持信息（如搜 "{股票名} 公告"、"{股票名} 高管减持"），不要因源失效就跳过排雷。',

  useCases: ['买入前排雷', '事件催化跟踪', '高管增减持信号'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位股票代码，如 600519',
      required: true,
      example: '002241',
    },
    kind: {
      type: 'string',
      description: '情报类型。announcements=公告；news=新闻；insider=内部人交易；all=全部（默认）',
      enum: ['announcements', 'news', 'insider', 'all'],
      example: 'all',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string' },
        available: { type: 'boolean' },
        announcements: { type: 'array' },
        news: { type: 'array' },
        insider_trades: { type: 'array' },
        summary: { type: 'string' },
        degraded_sources: { type: 'array' },
        note: { type: 'string' },
      },
    },
    render: (args, data) => {
      const lines: string[] = [`## 个股情报 ${data.symbol}`];
      if (!data.available) {
        lines.push(`⚠️ ${data.note || '情报源暂不可用'}`);
        if (data.degraded_sources?.length) lines.push(`降级源：${data.degraded_sources.join('；')}`);
        return [{ type: 'text', text: lines.join('\n') }];
      }
      if (data.summary) lines.push('', data.summary);
      if (data.announcements?.length) {
        lines.push('', '### 最新公告');
        for (const r of data.announcements.slice(0, 5)) {
          lines.push(`- ${r['公告日期'] || r['date'] || ''} ${r['公告标题'] || r['title'] || JSON.stringify(r).slice(0, 80)}`);
        }
      }
      if (data.news?.length) {
        lines.push('', '### 最新新闻');
        for (const r of data.news.slice(0, 5)) {
          lines.push(`- ${r['发布时间'] || ''} ${r['新闻标题'] || ''}`);
        }
      }
      if (data.insider_trades?.length) {
        lines.push('', '### 内部人交易');
        for (const r of data.insider_trades.slice(0, 5)) {
          lines.push(`- ${JSON.stringify(r).slice(0, 100)}`);
        }
      }
      if (data.degraded_sources?.length) lines.push('', `> ⚠️ 部分源降级：${data.degraded_sources.join('；')}`);
      return [{ type: 'text', text: lines.join('\n') }];
    },
  },
};
