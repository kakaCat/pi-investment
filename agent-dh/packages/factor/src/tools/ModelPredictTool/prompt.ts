/**
 * ModelPredictTool - ML 模型上涨概率预测
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ModelPredictParams {
  symbols: string[];
}

export const modelPredictPrompt: ToolPrompt<ModelPredictParams> = {
  name: 'model_predict',
  description: 'ML 模型（XGBoost）批量预测股票上涨概率与置信度。适用于：多标的打分时作为量化维度参考（与技术面/资金面/基本面并列的第 4 维度）。⚠️ 必须看 model_gate：level=degraded 表示模型接近随机水平，预测仅作弱参考；概率恒等 0.4659 说明因子数据缺失（输出不可信）。',

  parameters: {
    symbols: {
      type: 'array',
      description: '股票代码列表（6位数字），如 ["601857","600519"]，批量预测',
      required: true,
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
    '2026-09-01 上线（对接后端 /api/ml/predict，含上线门禁：test_accuracy<0.50 拒服、0.50~0.55 degraded）',
    '⚠️ 已知局限：DB 因子覆盖不足时输出恒定 0.4659（特征缺失补零所致）——遇到恒定概率说明输出不可信，等因子数据补齐',
    '预测是概率参考而非信号本身；C 级信号纪律：单一 ML 维度不构成买入依据',
    'confidence=low 时降低权重',
  ],

  relatedTools: [
    { name: 'factor_calculate', relationship: '技术因子计算', useCase: 'ML 特征同源因子' },
    { name: 'swing_points', relationship: '波段统计', useCase: '量化+波段双维度排序' },
  ],
};
