/**
 * ModelPredictTool - ML 模型上涨概率预测
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ModelPredictParams {
  symbols: string[];
  model_type?: string;
}

export const modelPredictPrompt: ToolPrompt<ModelPredictParams> = {
  name: 'model_predict',
  description: 'ML 模型（LightGBM，每日凌晨重训）批量预测股票上涨概率与置信度。适用于：多标的打分时作为量化维度参考（与技术面/资金面/基本面并列的第 4 维度）。⚠️ 模型目前是弱信号（test_roc_auc≈0.58、recall≈0.28），只能当辅助维度不能当决策驱动；model_gate level=degraded 时进一步降权。',

  parameters: {
    symbols: {
      type: 'array',
      description: '股票代码列表（6位数字），如 ["601857","600519"]，批量预测',
      required: true,
    },
    model_type: {
      type: 'string',
      description: "模型类型，默认 'lightgbm'（每日重训、特征与 DB 因子同源）。⚠️ 不要传 'xgboost'——2026-05 旧模型，特征名与 DB 因子不匹配，输出恒定 0.4659 不可信",
      default: 'lightgbm',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        predictions: { type: 'array', description: '预测列表（symbol/probability/confidence）' },
        model_gate: { type: 'object', additionalProperties: true, description: '模型质量门禁（level: normal/degraded）' },
      },
      additionalProperties: true,
    },
    render: (_args: ModelPredictParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      scenario: '批量预测候选股上涨概率',
      params: { symbols: ['601857', '600519', '300750'] },
      expectedBehavior: '返回每只股票的 probability（上涨概率）+ confidence + 模型门禁状态',
    },
  ],

  useCases: [
    { title: '量化维度参考', description: '多标的评分时作为第 4 维度（技术/资金/基本面之外）', example: 'symbols=[候选股列表]' },
    { title: '链式扫描加分项', description: '产业链批量扫描时辅助排序', example: '配合 swing_points 胜率一起排序' },
  ],

  notes: [
    '2026-09-01 上线；2026-09-02 修正默认模型为 lightgbm（xgboost 旧模型输出恒定 0.4659 的"DB 因子缺失"假象实为旧模型特征名不匹配）',
    '⚠️ 模型弱信号现实：test_accuracy≈0.57 / test_roc_auc≈0.58 / recall≈0.28——比随机好但有限，R-009 信号分级中 ML 只能算半个维度',
    '预测是概率参考而非信号本身；C 级信号纪律：单一 ML 维度不构成买入依据',
    'confidence=low 时降低权重；多标的概率接近时说明区分度不足',
    '因子数据最新日期见返回的 date 字段，滞后 >3 个交易日时提示数据陈旧',
  ],

  relatedTools: [
    { name: 'factor_calculate', relationship: '技术因子计算', useCase: 'ML 特征同源因子' },
    { name: 'swing_points', relationship: '波段统计', useCase: '量化+波段双维度排序' },
  ],
};
