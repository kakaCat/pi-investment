/**
 * 通用工具输出格式化工具库
 *
 * 统一所有 Agent 工具的输出格式，提供一致的用户体验。
 */

/**
 * 格式化表格数据
 * @param data 数据数组
 * @param columns 列定义
 * @param options 格式化选项
 */
export interface Column {
  key: string;
  label: string;
  width?: number;
  align?: 'left' | 'right' | 'center';
  format?: (value: any) => string;
}

export interface TableOptions {
  title?: string;
  maxRows?: number;
  showIndex?: boolean;
  emptyMessage?: string;
}

export function formatTableOutput(
  data: any[],
  columns: Column[],
  options: TableOptions = {}
): string {
  const {
    title,
    maxRows = 50,
    showIndex = false,
    emptyMessage = '暂无数据'
  } = options;

  if (!data || data.length === 0) {
    return emptyMessage;
  }

  const lines: string[] = [];

  // 标题
  if (title) {
    lines.push(`【${title}】`);
    lines.push('');
  }

  // 表头
  const headers = showIndex ? ['#', ...columns.map(c => c.label)] : columns.map(c => c.label);
  const colWidths = columns.map(c => c.width || 12);
  if (showIndex) colWidths.unshift(4);

  lines.push(headers.map((h, i) => h.padEnd(colWidths[i])).join(' | '));
  lines.push(colWidths.map(w => '-'.repeat(w)).join('-+-'));

  // 数据行
  const displayData = data.slice(0, maxRows);
  displayData.forEach((row, index) => {
    const cells = columns.map((col, i) => {
      const value = row[col.key];
      const formatted = col.format ? col.format(value) : String(value ?? '');
      const align = col.align || 'left';

      if (align === 'right') {
        return formatted.padStart(colWidths[showIndex ? i + 1 : i]);
      } else if (align === 'center') {
        const totalPad = colWidths[showIndex ? i + 1 : i] - formatted.length;
        const leftPad = Math.floor(totalPad / 2);
        const rightPad = totalPad - leftPad;
        return ' '.repeat(leftPad) + formatted + ' '.repeat(rightPad);
      } else {
        return formatted.padEnd(colWidths[showIndex ? i + 1 : i]);
      }
    });

    if (showIndex) {
      cells.unshift(String(index + 1).padEnd(4));
    }

    lines.push(cells.join(' | '));
  });

  // 截断提示
  if (data.length > maxRows) {
    lines.push('');
    lines.push(`（显示前 ${maxRows} 条，共 ${data.length} 条）`);
  }

  return lines.join('\n');
}

/**
 * 格式化列表数据
 * @param items 数据项数组
 * @param options 格式化选项
 */
export interface ListOptions {
  title?: string;
  maxItems?: number;
  bullet?: string;
  emptyMessage?: string;
  formatter?: (item: any, index: number) => string;
}

export function formatListOutput(
  items: any[],
  options: ListOptions = {}
): string {
  const {
    title,
    maxItems = 50,
    bullet = '•',
    emptyMessage = '暂无数据',
    formatter = (item: any) => String(item)
  } = options;

  if (!items || items.length === 0) {
    return emptyMessage;
  }

  const lines: string[] = [];

  // 标题
  if (title) {
    lines.push(`【${title}】`);
    lines.push('');
  }

  // 列表项
  const displayItems = items.slice(0, maxItems);
  displayItems.forEach((item, index) => {
    lines.push(`${bullet} ${formatter(item, index)}`);
  });

  // 截断提示
  if (items.length > maxItems) {
    lines.push('');
    lines.push(`（显示前 ${maxItems} 项，共 ${items.length} 项）`);
  }

  return lines.join('\n');
}

/**
 * 格式化键值对数据
 * @param data 键值对对象
 * @param options 格式化选项
 */
export interface KeyValueOptions {
  title?: string;
  keyWidth?: number;
  formatter?: Record<string, (value: any) => string>;
  excludeKeys?: string[];
  includeKeys?: string[];
}

export function formatKeyValueOutput(
  data: Record<string, any>,
  options: KeyValueOptions = {}
): string {
  const {
    title,
    keyWidth = 20,
    formatter = {},
    excludeKeys = [],
    includeKeys
  } = options;

  const lines: string[] = [];

  // 标题
  if (title) {
    lines.push(`【${title}】`);
    lines.push('');
  }

  // 键值对
  let keys = Object.keys(data);

  // 过滤键
  if (includeKeys) {
    keys = keys.filter(k => includeKeys.includes(k));
  }
  if (excludeKeys.length > 0) {
    keys = keys.filter(k => !excludeKeys.includes(k));
  }

  keys.forEach(key => {
    const value = data[key];
    const formattedValue = formatter[key]
      ? formatter[key](value)
      : formatValue(value);

    lines.push(`${key.padEnd(keyWidth)}: ${formattedValue}`);
  });

  return lines.join('\n');
}

/**
 * 格式化错误信息
 * @param error 错误对象或消息
 * @param context 上下文信息
 */
export interface ErrorContext {
  toolName?: string;
  command?: string;
  params?: any;
  suggestion?: string;
}

export function formatErrorOutput(
  error: Error | string,
  context?: ErrorContext
): string {
  const lines: string[] = [];

  // 错误标题
  lines.push('❌ 执行失败');
  lines.push('');

  // 工具/命令信息
  if (context?.toolName) {
    lines.push(`工具：${context.toolName}`);
  }
  if (context?.command) {
    lines.push(`命令：${context.command}`);
  }

  // 错误消息
  const errorMessage = error instanceof Error ? error.message : String(error);
  lines.push('');
  lines.push(`错误：${errorMessage}`);

  // 参数信息（仅在调试时显示）
  if (context?.params && Object.keys(context.params).length > 0) {
    lines.push('');
    lines.push('参数：');
    lines.push(JSON.stringify(context.params, null, 2));
  }

  // 建议
  if (context?.suggestion) {
    lines.push('');
    lines.push(`💡 建议：${context.suggestion}`);
  }

  return lines.join('\n');
}

/**
 * 格式化成功消息
 * @param message 消息内容
 * @param data 附加数据
 */
export interface SuccessOptions {
  title?: string;
  showData?: boolean;
}

export function formatSuccessOutput(
  message: string,
  data?: any,
  options: SuccessOptions = {}
): string {
  const { title = '执行成功', showData = false } = options;

  const lines: string[] = [];

  lines.push(`✅ ${title}`);
  lines.push('');
  lines.push(message);

  if (showData && data) {
    lines.push('');
    lines.push('详细信息：');
    lines.push(JSON.stringify(data, null, 2));
  }

  return lines.join('\n');
}

/**
 * 格式化进度信息
 * @param current 当前进度
 * @param total 总数
 * @param message 消息
 */
export function formatProgressOutput(
  current: number,
  total: number,
  message?: string
): string {
  const percentage = Math.round((current / total) * 100);
  const barLength = 30;
  const filledLength = Math.round((barLength * current) / total);
  const bar = '█'.repeat(filledLength) + '░'.repeat(barLength - filledLength);

  const lines: string[] = [];
  lines.push(`进度：[${bar}] ${percentage}% (${current}/${total})`);

  if (message) {
    lines.push(message);
  }

  return lines.join('\n');
}

/**
 * 格式化统计摘要
 * @param stats 统计数据
 */
export interface StatItem {
  label: string;
  value: number | string;
  format?: (value: any) => string;
  highlight?: boolean;
}

export function formatStatsOutput(
  stats: StatItem[],
  title?: string
): string {
  const lines: string[] = [];

  if (title) {
    lines.push(`【${title}】`);
    lines.push('');
  }

  const maxLabelWidth = Math.max(...stats.map(s => s.label.length));

  stats.forEach(stat => {
    const formattedValue = stat.format
      ? stat.format(stat.value)
      : String(stat.value);

    const prefix = stat.highlight ? '★' : ' ';
    lines.push(`${prefix} ${stat.label.padEnd(maxLabelWidth)}: ${formattedValue}`);
  });

  return lines.join('\n');
}

// ===== 辅助函数 =====

/**
 * 格式化单个值（智能类型检测）
 */
function formatValue(value: any): string {
  if (value === null || value === undefined) {
    return '-';
  }

  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }

  if (typeof value === 'number') {
    // 检测是否为百分比（0-1之间的小数）
    if (value > 0 && value < 1) {
      return `${(value * 100).toFixed(2)}%`;
    }
    // 检测是否为大数字（需要千分位）
    if (Math.abs(value) >= 1000) {
      return value.toLocaleString('zh-CN');
    }
    // 小数保留2位
    if (!Number.isInteger(value)) {
      return value.toFixed(2);
    }
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.length > 3
      ? `[${value.slice(0, 3).join(', ')}... (${value.length}项)]`
      : `[${value.join(', ')}]`;
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value);
    return keys.length > 3
      ? `{${keys.slice(0, 3).join(', ')}... (${keys.length}个字段)}`
      : JSON.stringify(value);
  }

  return String(value);
}

/**
 * 截断长文本
 */
export function truncateText(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength - 3) + '...';
}

/**
 * 格式化时间戳
 */
export function formatTimestamp(timestamp: string | number | Date): string {
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) {
    return String(timestamp);
  }
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

/**
 * 格式化数字（带单位）
 */
export function formatNumber(value: number, unit?: string, decimals: number = 2): string {
  const formatted = value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
  return unit ? `${formatted}${unit}` : formatted;
}

/**
 * 格式化百分比
 */
export function formatPercentage(value: number, decimals: number = 2): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * 格式化货币
 */
export function formatCurrency(value: number, currency: string = '¥'): string {
  return `${currency}${value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}
