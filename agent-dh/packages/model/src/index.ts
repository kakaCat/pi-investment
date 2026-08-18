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
 * ML Model Plugin for Agent-DH
 *
 * Model prediction, training, and evaluation.
 */
export default class ModelPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'model');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 模型预测
    ctx.tools.register(defineTool({
      name: 'model_predict',
      description: '用已训练的 ML 模型预测个股未来 N 个交易日的涨跌概率与预期收益，并给出影响最大的特征。适用于：辅助买卖决策、验证主观判断。注意：模型预测是概率参考而非确定性结论，应结合 confidence 与基本面/消息面综合判断，置信度低时不宜作为重仓依据。先用 model_evaluate 确认模型近期表现可靠。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        model_id: {
          type: 'string',
          description: '模型ID。不传则使用系统默认模型',
        },
        horizon: {
          type: 'integer',
          description: '预测周期（交易日），默认 5。与模型训练目标（target）一致时效果最好',
          default: 5,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            model_id: { type: 'string', description: '使用的模型ID' },
            up_probability: { type: 'number', description: '上涨概率（0-1）' },
            down_probability: { type: 'number', description: '下跌概率（0-1）' },
            expected_return: { type: 'number', description: '预期收益率（%）' },
            confidence: { type: 'number', description: '置信度（0-1）' },
            top_features: { type: 'array', description: '影响最大的特征' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        return qv2.predictWithModel({
          symbol: args.symbol,
          model_id: args.model_id,
          horizon: args.horizon || 5,
        }) as any;
      },
    } as any));

    // 模型训练
    ctx.tools.register(defineTool({
      name: 'model_train',
      description: '训练新的 ML 预测模型（耗时操作，最长等待 60 秒）。适用于：构建自定义预测模型、市场结构变化后重训练以保持模型有效性。训练完成后必须用 model_evaluate 验证效果再投入使用。',
      parameters: {
        model_type: {
          type: 'string',
          description: '模型类型。lgbm（LightGBM，推荐：训练快、表格数据表现好）；xgboost；random_forest；neural_net（神经网络，需要更多数据）',
          enum: ['lgbm', 'xgboost', 'random_forest', 'neural_net'],
          required: true,
        },
        name: {
          type: 'string',
          description: '模型名称，便于管理，如 v15-lgbm-value。不传则由系统生成',
        },
        symbols: {
          type: 'array',
          description: '训练样本股票列表，如 ["600519", "000001", "300750"]。样本越多样模型越稳健；不传则使用默认股票池',
          items: { type: 'string' },
        },
        features: {
          type: 'array',
          description: '特征列表，如 ["roe", "pe", "rsi", "macd", "turnover"]。不传则使用默认特征集。可用 factor_calculate 查看可选因子',
          items: { type: 'string' },
        },
        target: {
          type: 'string',
          description: '预测目标。return_5d（默认）：5日收益率；return_20d：20日收益率；direction：涨跌方向（分类问题）',
          enum: ['return_5d', 'return_20d', 'direction'],
          default: 'return_5d',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            model_id: { type: 'string', description: '新模型ID' },
            model_type: { type: 'string', description: '模型类型' },
            train_accuracy: { type: 'number', description: '训练集准确率' },
            val_accuracy: { type: 'number', description: '验证集准确率' },
            feature_importance: { type: 'array', description: '特征重要性排名' },
            status: { type: 'string', description: '状态：training/completed/failed' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        return qv2.trainModel({
          model_type: args.model_type,
          name: args.name,
          symbols: args.symbols,
          features: args.features,
          target: args.target || 'return_5d',
        }) as any;
      },
    } as any));

    // 模型评估
    ctx.tools.register(defineTool({
      name: 'model_evaluate',
      description: '评估模型在历史数据上的表现：准确率、精确率、AUC、夏普比率、最大回撤及评估结论。适用于：新模型上线前验证、定期检查存量模型是否失效需要重训练。',
      parameters: {
        model_id: {
          type: 'string',
          description: '模型ID，由 model_train 返回',
          required: true,
        },
        test_period: {
          type: 'string',
          description: '测试区间。recent_1m / recent_3m（默认）/ recent_6m：近期表现，反映对当前市场的适应性；all：全部历史，反映长期稳定性',
          enum: ['recent_1m', 'recent_3m', 'recent_6m', 'all'],
          default: 'recent_3m',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            model_id: { type: 'string', description: '模型ID' },
            accuracy: { type: 'number', description: '准确率' },
            precision: { type: 'number', description: '精确率' },
            recall: { type: 'number', description: '召回率' },
            f1_score: { type: 'number', description: 'F1分数' },
            auc: { type: 'number', description: 'AUC面积' },
            sharpe: { type: 'number', description: '策略夏普比率' },
            max_drawdown: { type: 'number', description: '最大回撤（%）' },
            conclusion: { type: 'string', description: '评估结论' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        return qv2.evaluateModel({
          model_id: args.model_id,
          test_period: args.test_period || 'recent_3m',
        }) as any;
      },
    } as any));
  }
}
