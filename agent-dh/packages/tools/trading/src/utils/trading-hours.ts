/**
 * 交易时段校验工具
 *
 * 宪法第 1 条：A股交易时段硬校验
 * 9:30-11:30 / 13:00-15:00（工作日）之外禁止下单
 */

import { ValidationResult, ErrorType } from '@pi-investment/core-tool';

/**
 * 检查是否在交易时段
 *
 * @param now 可注入时间（测试用），默认当前时间
 * @returns 校验结果
 */
export function validateTradingHours(now: Date = new Date()): ValidationResult {
  const day = now.getDay();
  const hh = now.getHours();
  const mm = now.getMinutes();
  const hhmm = hh * 100 + mm;

  // 检查是否周末
  if (day === 0 || day === 6) {
    return {
      success: false,
      errorType: ErrorType.BUSINESS_REJECTION,
      rule: '交易日限制',
      issue: '非交易日（周末）禁止下单',
      guide: '交易宪法第 1 条：仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托',
      currentTime: `${day === 0 ? '周日' : '周六'} ${hh}:${String(mm).padStart(2, '0')}`,
      solutions: [
        {
          approach: 'wait',
          description: '等待至下周一交易时段',
        },
        {
          approach: 'use_alternative',
          tool: 'watch_manage',
          reason: '可以设置价格提醒，在交易时段自动通知',
          example: 'watch_manage({ action: "create", name: "周一开盘提醒", condition: "price>0" })',
        },
      ],
    };
  }

  // 检查是否在交易时段内
  const inSession = (hhmm >= 930 && hhmm <= 1130) || (hhmm >= 1300 && hhmm <= 1500);

  if (!inSession) {
    return {
      success: false,
      errorType: ErrorType.BUSINESS_REJECTION,
      rule: '交易时段限制',
      issue: '当前非交易时段（9:30-11:30, 13:00-15:00）',
      guide: '盘前/盘后/夜间禁止买卖委托；分析与复盘不受限',
      currentTime: `${hh}:${String(mm).padStart(2, '0')}`,
      solutions: [
        {
          approach: 'wait',
          description: getNextTradingTime(now),
        },
        {
          approach: 'use_alternative',
          tool: 'watch_manage',
          reason: '可以设置价格提醒，在交易时段自动通知',
          example: 'watch_manage({ action: "create", name: "开盘提醒", condition: "price>0" })',
        },
      ],
    };
  }

  return { success: true };
}

/**
 * 获取下一个交易时段的时间
 */
function getNextTradingTime(now: Date): string {
  const hh = now.getHours();
  const mm = now.getMinutes();
  const hhmm = hh * 100 + mm;

  if (hhmm < 930) {
    return '等待至今日 09:30 开盘';
  } else if (hhmm > 1130 && hhmm < 1300) {
    return '等待至今日 13:00 午盘';
  } else if (hhmm >= 1500) {
    return '等待至明日 09:30 开盘';
  } else {
    return '等待至下一交易时段';
  }
}

/**
 * 断言交易时段（抛出异常版本，兼容旧代码）
 *
 * @deprecated 建议使用 validateTradingHours 返回 ValidationResult
 */
export function assertTradingHours(now: Date = new Date()): void {
  const result = validateTradingHours(now);
  if (!result.success) {
    throw new Error(result.issue);
  }
}
