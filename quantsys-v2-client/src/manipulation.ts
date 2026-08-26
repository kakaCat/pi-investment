/**
 * Stock Analysis Utilities
 * 
 * 共享的股票分析工具，供多个插件复用：
 * - detectManipulation: 操纵嫌疑检测（K线行为特征评分）
 * - chip_analysis: 筹码分析（未实现）
 */

import type { QuantsysV2Client } from './client.js';

export interface ManipulationDetectResult {
  symbol: string;
  manipulation_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'unknown';
  recommendation: 'normal' | 'watch' | 'avoid' | 'opportunity';
  detected_patterns: string[];
  evidence: string[];
  window_days: number;
  note?: string;
}

/**
 * 检测个股操纵嫌疑（拉高出货、对倒交易、诱多诱空等）
 * 
 * 基于 K 线行为特征计算嫌疑评分（0-100），越高嫌疑越大。
 * 
 * @param qv2 - QuantsysV2Client 实例
 * @param symbol - 股票代码（如 600519）
 * @param days - 分析窗口（默认 30 天）
 * @returns 嫌疑评分、检测模式、证据列表、操作建议
 */
export async function detectManipulation(
  qv2: QuantsysV2Client,
  symbol: string,
  days: number = 30
): Promise<ManipulationDetectResult> {
  const end = new Date();
  const start = new Date(end.getTime() - Math.max(days, 30) * 2 * 86400000);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  
  const klines: any[] = await qv2.getKlines(symbol, fmt(start), fmt(end), 'daily');
  
  if (!klines || klines.length < 10) {
    return {
      symbol,
      manipulation_score: 0,
      risk_level: 'unknown',
      recommendation: 'watch',
      detected_patterns: [],
      evidence: [`K线数据不足（${klines?.length ?? 0} 根），无法评估`],
      window_days: 0,
    };
  }

  const bars = klines.slice(-Math.max(days, 20));
  const last20 = klines.slice(-20);
  let score = 0;
  const patterns: string[] = [];
  const evidence: string[] = [];

  const pct = (a: number, b: number) => (b - a) / a * 100;
  const close0 = last20[0].close;
  const closeN = last20[last20.length - 1].close;
  
  const avgVol20 = last20.reduce((sum, k) => sum + (k.volume || 0), 0) / 20;

  // 1. 短期暴涨
  const chg20 = pct(close0, closeN);
  if (chg20 > 50) {
    score += 25;
    patterns.push('短期暴涨');
    evidence.push(`近20日涨幅 ${chg20.toFixed(1)}% > 50%`);
  }

  // 2. 连续涨停
  let limitUps = 0;
  for (let i = 1; i < bars.length; i++) {
    if (pct(bars[i - 1].close, bars[i].close) >= 9.9) limitUps++;
  }
  if (limitUps >= 3) {
    score += 20;
    patterns.push('连续涨停');
    evidence.push(`窗口内涨停 ${limitUps} 次（≥3）`);
  }

  // 3. 极端振幅
  let extremeAmp = 0;
  for (let i = 1; i < bars.length; i++) {
    const amp = (bars[i].high - bars[i].low) / bars[i - 1].close * 100;
    if (amp > 15) extremeAmp++;
  }
  if (extremeAmp >= 2) {
    score += 15;
    patterns.push('极端振幅');
    evidence.push(`单日振幅>15% 出现 ${extremeAmp} 次`);
  }

  // 4. 异常放量
  let volSpikes = 0;
  for (const k of bars) {
    if (avgVol20 > 0 && (k.volume || 0) / avgVol20 > 5) volSpikes++;
  }
  if (volSpikes >= 2) {
    score += 15;
    patterns.push('异常放量');
    evidence.push(`量比>5 的异常放量 ${volSpikes} 日（对倒嫌疑）`);
  }

  // 5. 放量急跌
  let dumpDays = 0;
  for (let i = 1; i < bars.length; i++) {
    const drop = pct(bars[i - 1].close, bars[i].close);
    const volRatio = avgVol20 > 0 ? (bars[i].volume || 0) / avgVol20 : 0;
    if (drop <= -7 && volRatio > 2) dumpDays++;
  }
  if (dumpDays >= 1) {
    score += 15;
    patterns.push('放量急跌');
    evidence.push(`放量急跌（≤-7%且量比>2）${dumpDays} 日`);
  }

  // 6. 崩盘后企稳
  let opportunity = false;
  const last5 = klines.slice(-5);
  if (chg20 < -30 && last5.length === 5) {
    const amp5 = (Math.max(...last5.map((k: any) => k.high)) - Math.min(...last5.map((k: any) => k.low))) / closeN * 100;
    if (amp5 < 10) {
      opportunity = true;
      patterns.push('崩盘后企稳');
      evidence.push(`20日跌幅 ${chg20.toFixed(1)}%，近5日振幅收敛至 ${amp5.toFixed(1)}%——操纵崩盘后的潜在机会窗口`);
    }
  }

  const risk = score > 70 ? 'high' : score >= 40 ? 'medium' : 'low';
  const recommendation = opportunity ? 'opportunity' : score > 70 ? 'avoid' : score >= 40 ? 'watch' : 'normal';

  return {
    symbol,
    manipulation_score: Math.min(100, score),
    risk_level: risk,
    recommendation,
    detected_patterns: patterns,
    evidence: evidence.length > 0 ? evidence : ['未发现显著操纵特征'],
    window_days: bars.length,
    note: '本地 K 线行为特征评分（M2-2 共享库）',
  };
}
