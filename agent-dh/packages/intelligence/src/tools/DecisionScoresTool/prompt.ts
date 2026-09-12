/**
 * DecisionScoresTool - 决策评分与教训查询工具（M6↔L2 回流边消费端）
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DecisionScoresParams {
  band?: 'big_loss' | 'big_win' | 'small_loss' | 'small_win';
  action?: 'buy' | 'sell' | 'skip';
  symbol?: string;
  since?: string;
  limit?: number;
  lessons_only?: boolean;
}

export const decisionScoresPrompt: ToolPrompt<DecisionScoresParams> = {
  description: '查询决策评分与教训（只读，M6↔L2 决策回流边的消费端）：拉取已完成评分的决策（含 20 交易日超额收益 band/score/excessReturn 与 learnedLesson），输出 band 分布、平均/最差/最好超额、教训覆盖率与明细。适用于：①盘前/盘后决策前必读（R-008 扩展：先看自己过去同类决策跑赢还是跑输基准）②复盘"为什么我的买入是负期望"③检查回流边是否断链（learnedLesson 覆盖率=0 即断）。',

  parameters: {
    band: {
      type: 'string',
      enum: ['big_loss', 'big_win', 'small_loss', 'small_win'],
      description: '按评分分级过滤：big_loss=大幅跑输基准 / big_win=大幅跑赢',
    },
    action: {
      type: 'string',
      enum: ['buy', 'sell', 'skip'],
      description: '按决策动作过滤（buy=trade_buy / sell=trade_sell / skip=skip_trade+missed_opportunity）',
    },
    symbol: {
      type: 'string',
      description: '按标的代码过滤（relatedEntityId），如 600150',
    },
    since: {
      type: 'string',
      description: '起始交易日 YYYY-MM-DD（按评价窗口的 tradeDate 过滤）',
    },
    limit: {
      type: 'integer',
      description: '返回明细条数上限（默认 20，汇总统计始终基于全量）',
    },
    lessons_only: {
      type: 'boolean',
      description: 'true=只返回 learnedLesson 非空的记录（查看已沉淀的教训）',
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        total: { type: 'integer', description: '评分记录总数' },
        matched: { type: 'integer', description: '过滤后条数' },
        summary: { type: 'object', additionalProperties: true, description: 'band 分布 / 平均超额 / 最差最好 / 教训覆盖率' },
        items: { type: 'array', description: '决策评分明细（含 learnedLesson）' },
      },
    },
    render: (_args: DecisionScoresParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      title: '盘前必读：我过去的买入决策跑赢基准了吗',
      params: { action: 'buy' },
      expectedResult: '返回买入类决策的 band 分布与平均超额；big_loss 占比高说明该方法负期望',
    },
    {
      title: '查最差的几笔决策及其教训',
      params: { band: 'big_loss', limit: 10 },
      expectedResult: '返回大幅跑输基准的决策明细与已沉淀教训（learnedLesson）',
    },
    {
      title: '检查回流边是否断链',
      params: {},
      expectedResult: 'summary.lessonCoverage.rate = 0 表示评分已产出但教训未回填（L2 断链）',
    },
  ],

  useCases: [
    '决策前必读（R-008 扩展）：下单/分析前先看同类决策的历史超额，避免重复负期望操作（action=buy + symbol=XXX）',
    '回流边健康检查：教训覆盖率为 0 或大量记录缺 learnedLesson → 上报 L2 断链（不带参数调一次看 summary）',
    '负期望归因输入：为"选股/择时/执行"三层归因提供量化底稿（band=big_loss 明细逐条看 context.regime/signal_source）',
  ],

  notes: [
    '2026-09-12 上线（REQ-9bcd0a WP2；client 方法 getEvolutionDecisionScores 早已存在，本工具补的是分析层与可达性）',
    '超额口径：窗口收益 - 同期基准收益（benchmark 默认 sh000300 / 000300），窗口 windowTradingDays 默认 20 交易日',
    'band 为评分器判定分档（decision_score_p0a），解读须结合 excessReturn 数值，不可只看标签',
    'learnedLesson 空值率是回流边健康指标：>0 且持续为空 = WP1 未落地或 L2 断链',
  ],

  relatedTools: [
    'decision_history：看决策推理原文与评估状态（时间线/待评估）',
    'decision_audit：记录决策并触发评估；有 pending 积压时用 evaluate 关闭',
    'signal_track：信号侧胜率，与决策评分互补（信号=入场点，评分=事后对错）',
  ],
};

