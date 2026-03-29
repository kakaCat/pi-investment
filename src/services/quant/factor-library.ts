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

export class FactorLibrary {
  /** 估值因子 - PE分位数 */
  valuationPE(pe: number, pePercentile: number): FactorScore {
    let score = 0;
    if (pePercentile < 20) score = 100;
    else if (pePercentile < 40) score = 80;
    else if (pePercentile < 60) score = 60;
    else if (pePercentile < 80) score = 40;
    else score = 20;

    return {
      name: '估值-PE',
      score,
      weight: 0.15,
      reason: `PE=${pe.toFixed(1)} 分位=${pePercentile.toFixed(0)}%`
    };
  }

  /** 估值因子 - PB */
  valuationPB(pb: number): FactorScore {
    let score = 0;
    if (pb < 1) score = 100;
    else if (pb < 2) score = 80;
    else if (pb < 3) score = 60;
    else if (pb < 5) score = 40;
    else score = 20;

    return {
      name: '估值-PB',
      score,
      weight: 0.10,
      reason: `PB=${pb.toFixed(2)}`
    };
  }

  /** 技术因子 - RSI */
  technicalRSI(rsi: number): FactorScore {
    let score = 0;
    if (rsi < 30) score = 100;
    else if (rsi < 40) score = 80;
    else if (rsi < 50) score = 60;
    else if (rsi < 70) score = 40;
    else score = 20;

    return {
      name: '技术-RSI',
      score,
      weight: 0.15,
      reason: `RSI=${rsi.toFixed(1)}`
    };
  }

  /** 技术因子 - 趋势 */
  technicalTrend(ma5: number, ma20: number, ma60: number): FactorScore {
    let score = 0;
    if (ma5 > ma20 && ma20 > ma60) score = 100;
    else if (ma5 > ma20) score = 70;
    else if (ma5 > ma60) score = 50;
    else score = 30;

    return {
      name: '技术-趋势',
      score,
      weight: 0.15,
      reason: `MA5>${ma20>ma60?'MA20>MA60':'MA60'}`
    };
  }

  /** 技术因子 - MACD */
  technicalMACD(histogram: number): FactorScore {
    const score = histogram > 0 ? 80 : 40;
    return {
      name: '技术-MACD',
      score,
      weight: 0.10,
      reason: `柱=${histogram.toFixed(4)}`
    };
  }

  /** 综合评分 */
  calculate(data: {
    pe?: number;
    pe_percentile?: number;
    pb?: number;
    rsi?: number;
    ma5?: number;
    ma20?: number;
    ma60?: number;
    macd_histogram?: number;
  }): FactorResult {
    const factors: FactorScore[] = [];

    // 估值因子
    if (data.pe && data.pe_percentile) {
      factors.push(this.valuationPE(data.pe, data.pe_percentile));
    }
    if (data.pb) {
      factors.push(this.valuationPB(data.pb));
    }

    // 技术因子
    if (data.rsi) {
      factors.push(this.technicalRSI(data.rsi));
    }
    if (data.ma5 && data.ma20 && data.ma60) {
      factors.push(this.technicalTrend(data.ma5, data.ma20, data.ma60));
    }
    if (data.macd_histogram !== undefined) {
      factors.push(this.technicalMACD(data.macd_histogram));
    }

    // 加权总分
    const totalScore = factors.reduce((sum, f) => sum + f.score * f.weight, 0) /
                       factors.reduce((sum, f) => sum + f.weight, 0);

    // 评级
    let grade: 'A' | 'B' | 'C' | 'D' | 'F';
    if (totalScore >= 80) grade = 'A';
    else if (totalScore >= 70) grade = 'B';
    else if (totalScore >= 60) grade = 'C';
    else if (totalScore >= 50) grade = 'D';
    else grade = 'F';

    return {
      symbol: '',
      total_score: totalScore,
      factors,
      grade
    };
  }
}
