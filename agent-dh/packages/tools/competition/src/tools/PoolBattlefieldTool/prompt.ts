/**
 * Pool Battlefield Tool Prompt
 *
 * 股票池战场评估（M2-3）：评估池子的竞争格局（散户/机构/游资三方强度），
 * 给出战场评分与攻防建议。博弈视角选股的核心工具——战场选错了，再好的策略也输。
 *
 * 2026-09-01 重建说明：初版（80ce5cfc）因 prompt 缺 parameters/output.schema 段
 * 导致 toDSHToolDefinition() 编译出 type:null schema，DSH 启动即崩（UNSUPPORTED_SCHEMA）。
 * 本版补齐显式 schema，每个 object 节点显式 additionalProperties（Schema 铁律）。
 * output schema 已与后端 GET /api/game/pools/{pool_id}/battlefield-assessment
 * 真实返回逐字段核实对齐。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface PoolBattlefieldParams {
  pool_id?: number;
  pool_name?: string;
}

export interface PoolBattlefieldResult {
  pool_id: number;
  pool_name: string;
  battlefield_score: number;
  opponent_strength: {
    retail_pressure: string;
    institution_interest: string;
    hot_money_risk: string;
  };
  game_phase: string;
  advantages: string[];
  disadvantages: string[];
  recommendation: string;
  urgency: string;
  confidence: number;
  data_quality: string;
}

export const poolBattlefieldPrompt: ToolPrompt<PoolBattlefieldParams, PoolBattlefieldResult> = {
  description: '评估股票池的竞争战场格局：三方对手强度（散户压力/机构兴趣/游资风险）、战场评分、博弈阶段与攻防建议。用于：选战场（优先低竞争高优势池子）、调仓前评估当前池子是否拥挤、识别机构撤退/散户追高信号。',

  useCases: [
    '盘前选择今日主战场（评分高+对手弱=好战场）',
    '持仓池子竞争恶化（游资涌入/机构撤退）时及时撤离',
    '对比多个池子的博弈优势，决定资金分配',
  ],

  examples: [
    {
      title: '按 ID 评估池子战场',
      params: { pool_id: 35 },
      expectedResult: '返回战场评分（0-100）、三方对手强度、博弈阶段与操作建议',
    },
    {
      title: '按名称评估池子战场',
      params: { pool_name: '高ROE价值池' },
      expectedResult: '自动解析池子 ID 后返回战场评估',
    },
  ],

  notes: [
    '💡 battlefield_score 越高=我方优势越大（非竞争激烈度）；<40 建议回避',
    '💡 recommendation: increase=加仓/hold=持有/reduce=减仓/exit=离场',
    '💡 game_phase: accumulation=吸筹/rising=主升/distribution=派发/decline=下跌',
    '⚠️ pool_id 与 pool_name 至少传一个；同时传时以 pool_id 为准',
  ],

  relatedTools: ['pool_list', 'competition_analysis'],

  parameters: {
    pool_id: {
      type: 'number',
      description: '股票池 ID（整数，如 35）。与 pool_name 二选一；pool_id 可通过 pool_list 工具获取',
      example: 35,
    },
    pool_name: {
      type: 'string',
      description: '股票池名称（模糊匹配，如 "高ROE"）。不知道 pool_id 时用名称查询',
      example: '高ROE价值池',
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        pool_id: { type: 'number', description: '池子 ID' },
        pool_name: { type: 'string', description: '池子名称（工具补充）' },
        battlefield_score: { type: 'number', description: '战场评分 0-100，越高=我方优势越大' },
        opponent_strength: {
          type: 'object',
          additionalProperties: false,
          properties: {
            retail_pressure: { type: 'string', description: '散户压力：low/medium/high' },
            institution_interest: { type: 'string', description: '机构兴趣：low/medium/high' },
            hot_money_risk: { type: 'string', description: '游资风险：low/medium/high' },
          },
        },
        game_phase: { type: 'string', description: '博弈阶段：accumulation/rising/distribution/decline' },
        advantages: { type: 'array', items: { type: 'string' }, description: '我方优势列表' },
        disadvantages: { type: 'array', items: { type: 'string' }, description: '我方劣势列表' },
        recommendation: { type: 'string', description: '操作建议：increase/hold/reduce/exit' },
        urgency: { type: 'string', description: '紧急程度：low/medium/high' },
        confidence: { type: 'number', description: '评估置信度 0-1' },
        data_quality: { type: 'string', description: '数据质量：full/partial/degraded' },
      },
    },
  },
};
