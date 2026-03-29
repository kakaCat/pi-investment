/**
 * 因子库 - 多维度评分
 */

export interface FactorScore {
  name: string;
  score: number;      // 0-100
  weight: number;     // 权重
  reason: string;
}

export interface FactorResult {
  symbol: string;
  total_score: number;
  factors: FactorScore[];
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
}

/** 可选权重覆盖，未指定的因子使用默认值 */
export interface FactorWeights {
  pe?: number;
  pb?: number;
  rsi?: number;
  trend?: number;
  macd?: number;
  momentum?: number;
  roe?: number;
  revenue_growth?: number;
}

const DEFAULT_WEIGHTS: Required<FactorWeights> = {
  pe: 0.20,
  pb: 0.10,
  rsi: 0.15,
  trend: 0.20,
  macd: 0.10,
  momentum: 0.25,
  roe: 0.15,           // 有数据时参与，权重归一化后自动生效
  revenue_growth: 0.10,
};

export class FactorLibrary {
  /** 估值因子 - PE分位数 */
  valuationPE(pe: number, pePercentile: number, weight?: number): FactorScore {
    let score = 0;
    if (pePercentile < 20) score = 100;
    else if (pePercentile < 40) score = 80;
    else if (pePercentile < 60) score = 60;
    else if (pePercentile < 80) score = 40;
    else score = 20;

    return {
      name: '估值-PE',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.pe,
      reason: `PE=${pe.toFixed(1)} 分位=${pePercentile.toFixed(0)}%`
    };
  }

  /** 估值因子 - PB */
  valuationPB(pb: number, weight?: number): FactorScore {
    let score = 0;
    if (pb < 1) score = 100;
    else if (pb < 2) score = 80;
    else if (pb < 3) score = 60;
    else if (pb < 5) score = 40;
    else score = 20;

    return {
      name: '估值-PB',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.pb,
      reason: `PB=${pb.toFixed(2)}`
    };
  }

  /** 技术因子 - RSI */
  technicalRSI(rsi: number, weight?: number): FactorScore {
    let score = 0;
    if (rsi < 30) score = 100;
    else if (rsi < 40) score = 80;
    else if (rsi < 50) score = 60;
    else if (rsi < 70) score = 40;
    else score = 20;

    return {
      name: '技术-RSI',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.rsi,
      reason: `RSI=${rsi.toFixed(1)}`
    };
  }

  /** 技术因子 - 趋势（均线多头排列） */
  technicalTrend(ma5: number, ma20: number, ma60: number, weight?: number): FactorScore {
    let score = 0;
    let reason = '';
    if (ma5 > ma20 && ma20 > ma60) {
      score = 100;
      reason = 'MA5>MA20>MA60 多头排列';
    } else if (ma5 > ma20 && ma20 <= ma60) {
      score = 70;
      reason = 'MA5>MA20 短期偏强';
    } else if (ma5 <= ma20 && ma5 > ma60) {
      score = 50;
      reason = 'MA5>MA60 中期支撑';
    } else {
      score = 30;
      reason = 'MA5<MA20<MA60 空头排列';
    }

    return {
      name: '技术-趋势',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.trend,
      reason,
    };
  }

  /** 技术因子 - MACD（区分强度和背离） */
  technicalMACD(histogram: number, prevHistogram?: number, weight?: number): FactorScore {
    let score = 0;
    let reason = `柱=${histogram.toFixed(4)}`;

    if (histogram > 0) {
      // 金叉后上升阶段
      if (prevHistogram !== undefined && histogram > prevHistogram) {
        score = 90;  // 柱状图扩大，动能增强
        reason += ' 动能增强';
      } else if (prevHistogram !== undefined && histogram < prevHistogram && histogram > 0) {
        score = 60;  // 顶背离预警：柱缩短但仍正值
        reason += ' 顶背离预警';
      } else {
        score = 80;  // 正值，无前值对比
      }
    } else {
      // 死叉后下降阶段
      if (prevHistogram !== undefined && histogram < prevHistogram) {
        score = 25;  // 柱状图继续扩大（更负），动能恶化
        reason += ' 空头动能增强';
      } else if (prevHistogram !== undefined && histogram > prevHistogram && histogram < 0) {
        score = 55;  // 底背离预警：柱缩短但仍负值
        reason += ' 底背离预警';
      } else {
        score = 40;  // 负值，无前值对比
      }
    }

    return {
      name: '技术-MACD',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.macd,
      reason,
    };
  }

  /** 动量因子
   * @param direction 'buy'（默认）正动量加分；'sell' 正动量减分（用于卖出判断）
   */
  momentum(changePct: number, weight?: number, direction: 'buy' | 'sell' = 'buy'): FactorScore {
    // 买入视角：适度上涨最优，超买/深跌均扣分
    const buyScore = (() => {
      if (changePct > 20) return 40;   // 短期超买，追高风险大
      if (changePct > 10) return 70;
      if (changePct > 0)  return 85;   // 温和上涨，最优
      if (changePct > -10) return 60;  // 小幅回调，可接受
      if (changePct > -20) return 40;  // 较大回调
      return 20;                        // 深度下跌
    })();

    const score = direction === 'sell' ? (100 - buyScore) : buyScore;

    return {
      name: '动量',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.momentum,
      reason: `20日涨跌=${changePct.toFixed(2)}% (${direction === 'sell' ? '卖出视角' : '买入视角'})`,
    };
  }

  /** 质量因子 - ROE */
  qualityROE(roe: number, weight?: number): FactorScore {
    let score = 0;
    if (roe >= 20) score = 100;
    else if (roe >= 15) score = 85;
    else if (roe >= 10) score = 65;
    else if (roe >= 5)  score = 40;
    else score = 20;

    return {
      name: '质量-ROE',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.roe,
      reason: `ROE=${roe.toFixed(1)}%`,
    };
  }

  /** 成长因子 - 营收增速 */
  growthRevenue(revenueGrowthPct: number, weight?: number): FactorScore {
    let score = 0;
    if (revenueGrowthPct >= 30) score = 100;
    else if (revenueGrowthPct >= 15) score = 85;
    else if (revenueGrowthPct >= 5)  score = 65;
    else if (revenueGrowthPct >= 0)  score = 45;
    else score = 20;  // 负增长

    return {
      name: '成长-营收',
      score,
      weight: weight ?? DEFAULT_WEIGHTS.revenue_growth,
      reason: `营收增速=${revenueGrowthPct.toFixed(1)}%`,
    };
  }

  /** 综合评分 */
  calculate(
    symbol: string,
    data: {
      // 估值
      pe?: number;
      pe_percentile?: number;
      pb?: number;
      // 技术
      rsi?: number;
      ma5?: number;
      ma20?: number;
      ma60?: number;
      macd_histogram?: number;
      macd_prev_histogram?: number;  // 上一根柱，用于判断背离/动能方向
      // 动量
      change_pct?: number;           // 近期（20日）涨跌幅
      direction?: 'buy' | 'sell';    // 动量因子视角，默认 buy
      // 基本面（需 Python bridge）
      roe?: number;
      revenue_growth?: number;
    },
    weights?: FactorWeights
  ): FactorResult {
    const w = { ...DEFAULT_WEIGHTS, ...weights };
    const factors: FactorScore[] = [];

    // 估值因子
    if (data.pe != null && data.pe > 0 && data.pe_percentile != null) {
      factors.push(this.valuationPE(data.pe, data.pe_percentile, w.pe));
    }
    if (data.pb != null && data.pb > 0) {
      factors.push(this.valuationPB(data.pb, w.pb));
    }

    // 技术因子
    if (data.rsi != null) {
      factors.push(this.technicalRSI(data.rsi, w.rsi));
    }
    if (data.ma5 != null && data.ma20 != null && data.ma60 != null) {
      factors.push(this.technicalTrend(data.ma5, data.ma20, data.ma60, w.trend));
    }
    if (data.macd_histogram != null) {
      factors.push(this.technicalMACD(data.macd_histogram, data.macd_prev_histogram, w.macd));
    }

    // 动量因子
    if (data.change_pct != null) {
      factors.push(this.momentum(data.change_pct, w.momentum, data.direction));
    }

    // 基本面因子（可选，有数据才参与）
    if (data.roe != null) {
      factors.push(this.qualityROE(data.roe, w.roe));
    }
    if (data.revenue_growth != null) {
      factors.push(this.growthRevenue(data.revenue_growth, w.revenue_growth));
    }

    if (factors.length === 0) {
      return { symbol, total_score: 0, factors: [], grade: 'F' };
    }

    // 加权总分（按实际参与因子的权重归一化）
    const totalWeight = factors.reduce((sum, f) => sum + f.weight, 0);
    const totalScore = factors.reduce((sum, f) => sum + f.score * f.weight, 0) / totalWeight;

    // 评级
    let grade: 'A' | 'B' | 'C' | 'D' | 'F';
    if (totalScore >= 80) grade = 'A';
    else if (totalScore >= 70) grade = 'B';
    else if (totalScore >= 60) grade = 'C';
    else if (totalScore >= 50) grade = 'D';
    else grade = 'F';

    return { symbol, total_score: Math.round(totalScore * 10) / 10, factors, grade };
  }
}
