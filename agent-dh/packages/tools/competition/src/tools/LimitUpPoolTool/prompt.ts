import type { ToolPrompt } from '@pi-investment/core-tool';

export interface LimitUpPoolParams {
  /** 日期 YYYY-MM-DD（默认今天，须为交易日） */
  date?: string;
  /** 最少连板数过滤（如 2=只看二连板以上） */
  min_streak?: number;
}

export interface LimitUpPoolResult {
  date: string;
  available: boolean;
  total?: number;
  max_streak?: number;
  streak_distribution?: Record<string, number>;
  records?: Array<Record<string, any>>;
  summary?: string;
  note?: string;
  [key: string]: any;
}

export const limitUpPoolPrompt: ToolPrompt<LimitUpPoolParams, LimitUpPoolResult> = {
  description: '涨停池查询（某日全部涨停股：连板数/封板资金/炸板次数/所属行业）。适用于：短线情绪温度计（涨停数量+连板高度=市场情绪）、识别游资抱团主线（同行业多只涨停=板块效应）、打板风险评估。解读参考：涨停>50家且最高连板≥5=情绪亢奋；涨停<20家=情绪冰点；炸板率高=分歧大。数据源为 akshare，非交易日无数据。',

  useCases: ['短线情绪判断', '游资抱团主线识别', '打板风险评估'],

  parameters: {
    date: {
      type: 'string',
      description: '日期 YYYY-MM-DD（默认今天），须为交易日',
      example: '2026-08-29',
    },
    min_streak: {
      type: 'number',
      description: '最少连板数过滤，如 2=只看二连板以上',
      example: 2,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        date: { type: 'string' },
        available: { type: 'boolean' },
        total: { type: 'number' },
        max_streak: { type: 'number' },
        streak_distribution: { type: 'object', additionalProperties: true },
        records: { type: 'array' },
        summary: { type: 'string' },
        note: { type: 'string' },
      },
    },
    render: (args, data) => {
      const lines: string[] = [`## 涨停池（${data.date}）`];
      if (!data.available) {
        lines.push(`⚠️ ${data.note || '无数据（非交易日或源不可用）'}`);
        return [{ type: 'text', text: lines.join('\n') }];
      }
      lines.push('', data.summary || '');
      if (data.streak_distribution) {
        lines.push('', '**连板分布**：' + Object.entries(data.streak_distribution)
          .sort((a, b) => Number(b[0]) - Number(a[0]))
          .map(([k, v]) => `${k}板×${v}`).join('，'));
      }
      lines.push('');
      for (const r of (data.records || []).slice(0, 20)) {
        lines.push(`- ${r['代码'] || ''} ${r['名称'] || ''} ${r['连板数'] ?? 1}连板 封单${r['封板资金'] ? Math.round(Number(r['封板资金']) / 1e4) + '万' : '?'} [${r['所属行业'] || '?'}]`);
      }
      return [{ type: 'text', text: lines.join('\n') }];
    },
  },
};
