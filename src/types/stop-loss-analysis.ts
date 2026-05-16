/**
 * 止损分析类型定义
 *
 * 止损分析引擎的输出类型。
 * 判断一个价格跌破到底是真破位（趋势反转）还是假洗盘（短期情绪）：
 * - 真破位 TRUE_BREAK: 放量跌破关键支撑 + 趋势确定空头 + 主力出逃 → 应止损
 * - 假洗盘 FALSE_BREAK: 缩量阴跌 + 趋势仍多头/震荡 + 主力未走 → 不应止损
 * - 中性 NEUTRAL: 矛盾信号 → 建议观察 1-2 个交易日
 */

/** 破位判定类型 */
export type BreakoutType = "TRUE_BREAK" | "FALSE_BREAK" | "NEUTRAL";

/** 建议操作 */
export type StopLossAction =
  | "STOP_LOSS"       // 真破位，建议立即止损
  | "HOLD_AND_WATCH"  // 假洗盘，建议持有观察
  | "WARN_AND_WATCH"  // 中性，建议高度警惕但暂不操作
  | "INSUFFICIENT_DATA"; // 数据不足，建议按原止损纪律执行

/** 分析请求 */
export interface StopLossAnalysisRequest {
  symbol: string;
  name: string;
  currentPrice: number;
  costPrice: number;
  stopLossPrice: number;
  market: "A" | "HK";
}

/** 证据链条目 */
export interface EvidenceItem {
  source: string;           // 数据来源工具名，如 "get_stock_history"
  summary: string;          // 证据要点
  detail: string;           // 原始数据片段
}

/** 技术面分析结果 */
export interface TechnicalAnalysis {
  trend: string;            // "上升" / "下降" / "震荡" / "无法判断"
  trendConfirmed: boolean;  // 趋势是否确认（60日均线方向明确）
  supportLevel: number | null; // 最近的关键支撑位
  resistanceLevel: number | null; // 最近的关键阻力位
  pattern: string | null;   // K线形态
  rsi: number | null;       // RSI-14
  macdSignal: string | null; // MACD信号
  evidence: EvidenceItem[];
}

/** 成交量分析结果 */
export interface VolumeAnalysis {
  vsAvgVolume: number | null;  // 今日量 / 20日均量（百分比）
  isShrink: boolean | null;    // 是否缩量（< 80%均量）
  isVolumeSpike: boolean | null; // 是否放量（> 150%均量）
  evidence: EvidenceItem[];
}

/** 资金面分析结果 */
export interface FundFlowAnalysis {
  mainForceNetFlow: string | null; // "净流入" / "净流出" / "无明显信号"
  retailBuyRatio: string | null;   // 散户买入比例
  evidence: EvidenceItem[];
}

/** 基本面检查结果 */
export interface FundamentalCheck {
  hasRecentNegativeNews: boolean | null; // 近期是否有负面消息
  hasRecentPositiveNews: boolean | null; // 近期是否有正面消息
  earningsWarning: boolean | null;       // 是否有业绩预警
  newsSummary: string;
  evidence: EvidenceItem[];
}

/** 完整止损分析报告 */
export interface StopLossReport {
  request: StopLossAnalysisRequest;
  analyzedAt: string;            // 分析时间

  // 各维度分析
  technical: TechnicalAnalysis;
  volume: VolumeAnalysis;
  fundFlow: FundFlowAnalysis;
  fundamentals: FundamentalCheck;

  // 综合判断
  breakoutType: BreakoutType;
  confidence: number;            // 0-100，置信度
  suggestedAction: StopLossAction;
  actionReason: string;          // 为什么给出这个建议
  riskNote: string;              // 风险提示

  // 全证据链
  evidenceChain: EvidenceItem[];
}
