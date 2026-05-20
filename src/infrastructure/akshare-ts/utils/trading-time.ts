/**
 * Trading time utilities - detect trading hours and provide fallback strategies
 */

export interface TradingTimeInfo {
  isTradingDay: boolean;
  isTradingHours: boolean;
  isWeekend: boolean;
  currentTime: string;
  reason: string;
  alternatives: string[];
}

/**
 * Check if current time is within A-share trading hours
 * Trading hours: Mon-Fri 9:30-11:30, 13:00-15:00 (China timezone)
 */
export function getTradingTimeInfo(): TradingTimeInfo {
  const now = new Date();

  // Convert to China timezone (UTC+8)
  const chinaTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
  const dayOfWeek = chinaTime.getDay(); // 0=Sunday, 6=Saturday
  const hours = chinaTime.getHours();
  const minutes = chinaTime.getMinutes();
  const currentMinutes = hours * 60 + minutes;

  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
  const isTradingDay = !isWeekend; // Simplified: not checking holidays

  // Trading hours: 9:30-11:30 (570-690 min), 13:00-15:00 (780-900 min)
  const morningStart = 9 * 60 + 30; // 570
  const morningEnd = 11 * 60 + 30; // 690
  const afternoonStart = 13 * 60; // 780
  const afternoonEnd = 15 * 60; // 900

  const isTradingHours = isTradingDay && (
    (currentMinutes >= morningStart && currentMinutes <= morningEnd) ||
    (currentMinutes >= afternoonStart && currentMinutes <= afternoonEnd)
  );

  const currentTime = chinaTime.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });

  let reason = '';
  const alternatives: string[] = [];

  if (isWeekend) {
    reason = '周末非交易时段，数据源响应缓慢或不可用';
    alternatives.push('使用已知基本面数据（ROE/毛利率/负债率）进行初步筛选');
    alternatives.push('基于行业和市值进行定性分析');
    alternatives.push('建议交易日 9:30-15:00 重新运行深度分析');
  } else if (!isTradingHours) {
    if (currentMinutes < morningStart) {
      reason = '盘前时段，数据源可能未更新';
      alternatives.push('等待 9:30 开盘后重试');
    } else if (currentMinutes > afternoonEnd) {
      reason = '盘后时段，部分数据源响应较慢';
      alternatives.push('使用缓存数据或基本面知识');
      alternatives.push('次日交易时段重新获取最新数据');
    } else {
      reason = '午间休市时段';
      alternatives.push('等待 13:00 开盘后重试');
    }
  }

  return {
    isTradingDay,
    isTradingHours,
    isWeekend,
    currentTime,
    reason,
    alternatives
  };
}

/**
 * Generate a user-friendly error message with alternatives
 */
export function generateTimeoutAlternatives(symbol: string, toolName: string): string {
  const timeInfo = getTradingTimeInfo();

  return JSON.stringify({
    error: `数据源超时（${timeInfo.reason}）`,
    symbol,
    tool: toolName,
    time_info: {
      current_time: timeInfo.currentTime,
      is_trading_hours: timeInfo.isTradingHours,
      is_weekend: timeInfo.isWeekend
    },
    alternatives: timeInfo.alternatives,
    suggestion: timeInfo.isTradingHours
      ? '数据源临时不可用，建议稍后重试或使用替代数据源'
      : `建议在交易时段（周一至周五 9:30-15:00）重新运行以获取完整数据`
  });
}
