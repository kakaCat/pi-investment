/**
 * 因子分析服务
 *
 * 提供因子重要性分析和单股因子贡献分析
 * 调用Python量化系统的分析脚本
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { readFile, access } from 'fs/promises';
import path from 'path';

const execAsync = promisify(exec);

export interface FactorImportance {
  feature: string;
  importance: number;
  percentage: number;
  cumulative: number;
}

export interface StockFactorContribution {
  name: string;
  value: number;
  importance: number;
  contribution: number;
}

export interface StockFactorAnalysis {
  symbol: string;
  date: string;
  price: number;
  prediction: {
    up_probability: number;
    direction: 'UP' | 'DOWN';
    confidence: number;
  };
  key_factors: StockFactorContribution[];
  interpretation: string[];
}

export interface FeatureImportanceResult {
  top_features: FactorImportance[];
  total_features: number;
  top_20_percent_count: number;
  analysis_date: string;
}

export class FactorAnalysisService {
  private quantDir: string;
  private cacheDir: string;

  constructor(quantDir: string = 'quant') {
    this.quantDir = path.resolve(quantDir);
    this.cacheDir = path.join(this.quantDir, '.pi-invest');
  }

  /**
   * 获取整体因子重要性分析
   */
  async getFeatureImportance(): Promise<FeatureImportanceResult> {
    try {
      // 检查是否有缓存的CSV文件
      const csvPath = path.join(this.cacheDir, 'feature_importance.csv');

      try {
        await access(csvPath);
        // 读取CSV
        const csvContent = await readFile(csvPath, 'utf-8');
        const lines = csvContent.trim().split('\n');

        if (lines.length < 2) {
          throw new Error('Empty CSV file');
        }

        // 解析CSV（跳过header）
        const features: FactorImportance[] = [];
        for (let i = 1; i < lines.length; i++) {
          const [feature, importance, percentage, cumulative] = lines[i].split(',');
          features.push({
            feature: feature.trim(),
            importance: parseFloat(importance),
            percentage: parseFloat(percentage),
            cumulative: parseFloat(cumulative)
          });
        }

        // 找出前20%的因子数量
        const top20Count = features.filter(f => f.cumulative <= 80).length;

        return {
          top_features: features.slice(0, 15), // 返回前15个
          total_features: features.length,
          top_20_percent_count: top20Count,
          analysis_date: new Date().toISOString()
        };

      } catch (error) {
        // 缓存不存在，运行Python脚本
        console.log('[FactorAnalysis] Running feature importance analysis...');

        const { stdout, stderr } = await execAsync(
          'python3 scripts/analyze_feature_importance.py',
          { cwd: this.quantDir }
        );

        if (stderr && !stderr.includes('zoxide')) {
          console.warn('[FactorAnalysis] stderr:', stderr);
        }

        // 重新读取生成的CSV
        return this.getFeatureImportance();
      }

    } catch (error) {
      console.error('[FactorAnalysis] Failed to get feature importance:', error);
      throw new Error(`因子重要性分析失败: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * 分析单只股票的因子贡献
   */
  async analyzeStockFactors(
    symbol: string,
    date?: string
  ): Promise<StockFactorAnalysis> {
    try {
      console.log(`[FactorAnalysis] Analyzing factors for ${symbol}...`);

      // 运行Python分析脚本
      const cmd = date
        ? `python3 scripts/analyze_stock_factors.py ${symbol} ${date}`
        : `python3 scripts/analyze_stock_factors.py ${symbol}`;

      const { stdout, stderr } = await execAsync(cmd, { cwd: this.quantDir });

      if (stderr && !stderr.includes('zoxide')) {
        console.warn('[FactorAnalysis] stderr:', stderr);
      }

      // 解析输出
      const lines = stdout.split('\n');

      // 提取关键信息
      let actualDate = date || '';
      let price = 0;
      let upProbability = 0;
      const keyFactors: StockFactorContribution[] = [];

      for (const line of lines) {
        if (line.includes('分析日期:')) {
          actualDate = line.split(':')[1].trim();
        } else if (line.includes('当前价格:')) {
          price = parseFloat(line.match(/¥([\d.]+)/)?.[1] || '0');
        } else if (line.includes('预测上涨概率:')) {
          const match = line.match(/([\d.]+)%/);
          if (match) {
            upProbability = parseFloat(match[1]) / 100;
          }
        }
      }

      // 读取生成的CSV文件
      const csvPath = path.join(this.cacheDir, `factor_analysis_${symbol}_${actualDate}.csv`);

      try {
        const csvContent = await readFile(csvPath, 'utf-8');
        const csvLines = csvContent.trim().split('\n');

        // 解析前5个因子
        for (let i = 1; i <= Math.min(6, csvLines.length - 1); i++) {
          const parts = csvLines[i].split(',');
          if (parts.length >= 4) {
            keyFactors.push({
              name: parts[0].trim(),
              value: parseFloat(parts[1]),
              importance: parseFloat(parts[2] || '0'),
              contribution: parseFloat(parts[3] || parts[2] || '0') // SHAP或Contribution
            });
          }
        }
      } catch (error) {
        console.warn('[FactorAnalysis] Could not read CSV, using default factors');
      }

      // 生成解读
      const interpretation = this.interpretFactors(keyFactors, upProbability);

      return {
        symbol,
        date: actualDate,
        price,
        prediction: {
          up_probability: upProbability,
          direction: upProbability > 0.5 ? 'UP' : 'DOWN',
          confidence: Math.abs(upProbability - 0.5) * 2
        },
        key_factors: keyFactors,
        interpretation
      };

    } catch (error) {
      console.error(`[FactorAnalysis] Failed to analyze ${symbol}:`, error);
      throw new Error(`股票因子分析失败: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * 批量分析多只股票
   */
  async analyzeMultipleStocks(
    symbols: string[],
    date?: string
  ): Promise<StockFactorAnalysis[]> {
    const results: StockFactorAnalysis[] = [];

    for (const symbol of symbols) {
      try {
        const analysis = await this.analyzeStockFactors(symbol, date);
        results.push(analysis);
      } catch (error) {
        console.warn(`[FactorAnalysis] Failed to analyze ${symbol}:`, error);
        // 继续处理其他股票
      }
    }

    return results;
  }

  /**
   * 解释因子含义
   */
  private interpretFactors(
    factors: StockFactorContribution[],
    upProbability: number
  ): string[] {
    const interpretations: string[] = [];

    // 整体判断
    if (upProbability > 0.7) {
      interpretations.push('📈 强烈看涨信号');
    } else if (upProbability > 0.6) {
      interpretations.push('📈 看涨信号');
    } else if (upProbability > 0.4) {
      interpretations.push('➡️ 中性信号');
    } else if (upProbability > 0.3) {
      interpretations.push('📉 看跌信号');
    } else {
      interpretations.push('📉 强烈看跌信号');
    }

    // 分析关键因子
    for (const factor of factors.slice(0, 3)) {
      const direction = factor.contribution > 0 ? '看涨' : '看跌';
      const strength = Math.abs(factor.contribution);

      if (factor.name === 'RSI') {
        if (factor.value < 30) {
          interpretations.push(`RSI=${factor.value.toFixed(1)} 超卖，${direction}因素`);
        } else if (factor.value > 70) {
          interpretations.push(`RSI=${factor.value.toFixed(1)} 超买，${direction}因素`);
        } else {
          interpretations.push(`RSI=${factor.value.toFixed(1)} 中性，${direction}因素`);
        }
      } else if (factor.name.includes('MA')) {
        if (factor.value > 1) {
          interpretations.push(`均线多头排列，${direction}因素`);
        } else {
          interpretations.push(`均线空头排列，${direction}因素`);
        }
      } else if (factor.name === 'Volume_Ratio') {
        if (factor.value > 1.2) {
          interpretations.push(`成交量放大，${direction}因素`);
        } else if (factor.value < 0.8) {
          interpretations.push(`成交量萎缩，${direction}因素`);
        }
      } else if (factor.name === 'BB_Position') {
        if (factor.value > 0.8) {
          interpretations.push(`价格接近布林带上轨，${direction}因素`);
        } else if (factor.value < 0.2) {
          interpretations.push(`价格接近布林带下轨，${direction}因素`);
        }
      }
    }

    return interpretations;
  }

  /**
   * 获取因子解释文档
   */
  getFactorExplanations(): Record<string, string> {
    return {
      'RSI': 'RSI相对强弱指标：<30超卖，>70超买',
      'MACD_DIF': 'MACD快线：>0金叉看涨，<0死叉看跌',
      'MA5/MA20': '短期均线比：>1短期强势，<1短期弱势',
      'Price/MA5': '价格相对5日线：>1在均线上方，<1在均线下方',
      'BB_Position': '布林带位置：>0.8接近上轨，<0.2接近下轨',
      'Volume_Ratio': '成交量比率：>1.2放量，<0.8缩量',
      'KDJ_K': 'KDJ指标K值：<20超卖，>80超买',
      'MFI': '资金流量指标：<20超卖，>80超买',
      'ATR_Ratio': '波动率指标：数值越大波动越大',
      'ROC': '变动率指标：>0上涨动能，<0下跌动能'
    };
  }
}
