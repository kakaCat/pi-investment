/**
 * K线数据质量验证和清洗模块
 *
 * 提供数据验证、清洗和质量日志记录功能
 */

import { writeFileSync, appendFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { getSessionDir } from '../../logging/observable-logger.js';
import type { KlineDataPoint } from './types.js';

// ─── 类型定义 ────────────────────────────────────────────

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface ValidationError {
  type: 'missing_field' | 'invalid_value' | 'inconsistent_data' | 'duplicate';
  field?: string;
  index?: number;
  value?: any;
  message: string;
}

export interface ValidationWarning {
  type: 'outlier' | 'suspicious_value' | 'gap' | 'inconsistent_data';
  field?: string;
  index?: number;
  value?: any;
  message: string;
}

export interface CleaningResult {
  cleaned: KlineDataPoint[];
  removed: number;
  fixed: number;
  operations: CleaningOperation[];
}

export interface CleaningOperation {
  type: 'remove' | 'fix' | 'fill';
  index: number;
  field?: string;
  originalValue?: any;
  newValue?: any;
  reason: string;
}

export interface QualityMetrics {
  totalRecords: number;
  validRecords: number;
  invalidRecords: number;
  completeness: number; // 0-1
  consistency: number; // 0-1
  accuracy: number; // 0-1
  overall: number; // 0-1
}

export interface QualityLog {
  timestamp: string;
  symbol: string;
  period: string;
  requestedRange: {
    startDate?: string;
    endDate?: string;
    limit?: number;
  };
  validation: ValidationResult;
  cleaning: CleaningResult;
  metrics: QualityMetrics;
  durationMs: number;
}

// ─── 验证规则 ────────────────────────────────────────────

/**
 * 验证K线数据质量
 */
export function validateKlineData(data: KlineDataPoint[]): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationWarning[] = [];

  // 防御非数组输入：v2 API 在异常/未就绪时可能返回对象或错误体，
  // 直接 .forEach 会抛 "data.forEach is not a function"。
  if (!data || !Array.isArray(data) || data.length === 0) {
    return {
      isValid: true,
      errors: [],
      warnings: [{ type: 'gap', message: Array.isArray(data) ? '数据为空' : '数据格式异常（非数组）' }],
    };
  }

  const seenDates = new Set<string>();

  data.forEach((point, index) => {
    // 1. 必填字段检查
    const requiredFields: Array<keyof KlineDataPoint> = ['date', 'open', 'high', 'low', 'close', 'volume'];
    for (const field of requiredFields) {
      if (point[field] === undefined || point[field] === null) {
        errors.push({
          type: 'missing_field',
          field,
          index,
          message: `缺少必填字段: ${field}`,
        });
      }
    }

    // 2. 数值合理性检查
    if (point.open !== undefined && point.open <= 0) {
      errors.push({
        type: 'invalid_value',
        field: 'open',
        index,
        value: point.open,
        message: `开盘价必须大于0: ${point.open}`,
      });
    }

    if (point.high !== undefined && point.high <= 0) {
      errors.push({
        type: 'invalid_value',
        field: 'high',
        index,
        value: point.high,
        message: `最高价必须大于0: ${point.high}`,
      });
    }

    if (point.low !== undefined && point.low <= 0) {
      errors.push({
        type: 'invalid_value',
        field: 'low',
        index,
        value: point.low,
        message: `最低价必须大于0: ${point.low}`,
      });
    }

    if (point.close !== undefined && point.close <= 0) {
      errors.push({
        type: 'invalid_value',
        field: 'close',
        index,
        value: point.close,
        message: `收盘价必须大于0: ${point.close}`,
      });
    }

    if (point.volume !== undefined && point.volume < 0) {
      errors.push({
        type: 'invalid_value',
        field: 'volume',
        index,
        value: point.volume,
        message: `成交量不能为负: ${point.volume}`,
      });
    }

    // 3. 数据一致性检查（最高价 >= 最低价，最高价 >= 开盘价/收盘价）
    if (
      point.high !== undefined &&
      point.low !== undefined &&
      point.high < point.low
    ) {
      errors.push({
        type: 'inconsistent_data',
        index,
        message: `最高价(${point.high})不能低于最低价(${point.low})`,
      });
    }

    if (
      point.high !== undefined &&
      point.open !== undefined &&
      point.high < point.open
    ) {
      warnings.push({
        type: 'inconsistent_data',
        index,
        message: `最高价(${point.high})低于开盘价(${point.open})，可能异常`,
      });
    }

    if (
      point.high !== undefined &&
      point.close !== undefined &&
      point.high < point.close
    ) {
      warnings.push({
        type: 'inconsistent_data',
        index,
        message: `最高价(${point.high})低于收盘价(${point.close})，可能异常`,
      });
    }

    if (
      point.low !== undefined &&
      point.open !== undefined &&
      point.low > point.open
    ) {
      warnings.push({
        type: 'inconsistent_data',
        index,
        message: `最低价(${point.low})高于开盘价(${point.open})，可能异常`,
      });
    }

    if (
      point.low !== undefined &&
      point.close !== undefined &&
      point.low > point.close
    ) {
      warnings.push({
        type: 'inconsistent_data',
        index,
        message: `最低价(${point.low})高于收盘价(${point.close})，可能异常`,
      });
    }

    // 4. 重复日期检查
    if (point.date) {
      if (seenDates.has(point.date)) {
        errors.push({
          type: 'duplicate',
          field: 'date',
          index,
          value: point.date,
          message: `日期重复: ${point.date}`,
        });
      }
      seenDates.add(point.date);
    }

    // 5. 异常值检测（价格暴涨暴跌 > 30%）
    if (index > 0 && point.close !== undefined && data[index - 1].close !== undefined) {
      const prevClose = data[index - 1].close;
      const changePercent = Math.abs((point.close - prevClose) / prevClose) * 100;
      if (changePercent > 30) {
        warnings.push({
          type: 'outlier',
          field: 'close',
          index,
          value: point.close,
          message: `价格变动异常: ${changePercent.toFixed(2)}%（前收${prevClose} → 当前${point.close}）`,
        });
      }
    }

    // 6. 成交量异常检测（为0或异常大）
    if (point.volume === 0) {
      warnings.push({
        type: 'suspicious_value',
        field: 'volume',
        index,
        value: 0,
        message: '成交量为0，可能是停牌或数据缺失',
      });
    }

    if (index > 0 && point.volume !== undefined && data[index - 1].volume !== undefined) {
      const avgVolume = data.slice(Math.max(0, index - 5), index)
        .reduce((sum, p) => sum + (p.volume || 0), 0) / Math.min(5, index);
      if (avgVolume > 0 && point.volume > avgVolume * 10) {
        warnings.push({
          type: 'outlier',
          field: 'volume',
          index,
          value: point.volume,
          message: `成交量异常放大: ${(point.volume / avgVolume).toFixed(2)}倍`,
        });
      }
    }
  });

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
}

// ─── 数据清洗 ────────────────────────────────────────────

/**
 * 清洗K线数据
 */
export function cleanKlineData(
  data: KlineDataPoint[],
  validation: ValidationResult
): CleaningResult {
  const operations: CleaningOperation[] = [];
  let cleaned: KlineDataPoint[] = [];
  let removed = 0;
  let fixed = 0;

  // 收集需要移除的索引
  const indicesToRemove = new Set<number>();

  // 1. 标记严重错误的数据点（缺少必填字段、无效值）
  validation.errors.forEach((error) => {
    if (error.index !== undefined) {
      if (
        error.type === 'missing_field' ||
        error.type === 'invalid_value' ||
        error.type === 'duplicate'
      ) {
        indicesToRemove.add(error.index);
        operations.push({
          type: 'remove',
          index: error.index,
          field: error.field,
          reason: error.message,
        });
      }
    }
  });

  // 2. 处理不一致数据（尝试修复）
  data.forEach((point, index) => {
    if (indicesToRemove.has(index)) return;

    let fixedPoint = { ...point };
    let hasFixed = false;

    // 修复：最高价 < 最低价
    if (fixedPoint.high < fixedPoint.low) {
      const temp = fixedPoint.high;
      fixedPoint.high = fixedPoint.low;
      fixedPoint.low = temp;
      operations.push({
        type: 'fix',
        index,
        field: 'high/low',
        originalValue: { high: point.high, low: point.low },
        newValue: { high: fixedPoint.high, low: fixedPoint.low },
        reason: '交换了最高价和最低价',
      });
      hasFixed = true;
    }

    // 修复：最高价 < 开盘价或收盘价（调整最高价）
    if (fixedPoint.high < fixedPoint.open || fixedPoint.high < fixedPoint.close) {
      const newHigh = Math.max(fixedPoint.open, fixedPoint.close, fixedPoint.high);
      operations.push({
        type: 'fix',
        index,
        field: 'high',
        originalValue: fixedPoint.high,
        newValue: newHigh,
        reason: `最高价调整为开盘价/收盘价中的最大值`,
      });
      fixedPoint.high = newHigh;
      hasFixed = true;
    }

    // 修复：最低价 > 开盘价或收盘价（调整最低价）
    if (fixedPoint.low > fixedPoint.open || fixedPoint.low > fixedPoint.close) {
      const newLow = Math.min(fixedPoint.open, fixedPoint.close, fixedPoint.low);
      operations.push({
        type: 'fix',
        index,
        field: 'low',
        originalValue: fixedPoint.low,
        newValue: newLow,
        reason: `最低价调整为开盘价/收盘价中的最小值`,
      });
      fixedPoint.low = newLow;
      hasFixed = true;
    }

    if (hasFixed) {
      fixed++;
    }

    cleaned.push(fixedPoint);
  });

  removed = indicesToRemove.size;

  return {
    cleaned,
    removed,
    fixed,
    operations,
  };
}

// ─── 质量指标计算 ────────────────────────────────────────

/**
 * 计算数据质量指标
 */
export function calculateQualityMetrics(
  originalCount: number,
  validation: ValidationResult,
  cleaning: CleaningResult
): QualityMetrics {
  const totalRecords = originalCount;
  const validRecords = cleaning.cleaned.length;
  const invalidRecords = cleaning.removed;

  // 完整性：有效记录占比
  const completeness = totalRecords > 0 ? validRecords / totalRecords : 0;

  // 一致性：无一致性错误的记录占比
  const inconsistencyErrors = validation.errors.filter(
    (e) => e.type === 'inconsistent_data'
  ).length;
  const consistency =
    totalRecords > 0 ? 1 - inconsistencyErrors / totalRecords : 1;

  // 准确性：无异常值告警的记录占比
  const outlierWarnings = validation.warnings.filter(
    (w) => w.type === 'outlier'
  ).length;
  const accuracy = totalRecords > 0 ? 1 - outlierWarnings / totalRecords : 1;

  // 综合评分（加权平均）
  const overall = completeness * 0.4 + consistency * 0.3 + accuracy * 0.3;

  return {
    totalRecords,
    validRecords,
    invalidRecords,
    completeness,
    consistency,
    accuracy,
    overall,
  };
}

// ─── 质量日志 ────────────────────────────────────────────

/**
 * 记录数据质量日志
 */
export function logDataQuality(log: QualityLog): void {
  try {
    // 1. 保存到会话目录（文件系统）
    const sessionDir = getSessionDir();
    if (sessionDir) {
      const qualityDir = join(sessionDir, 'data-quality');
      if (!existsSync(qualityDir)) {
        mkdirSync(qualityDir, { recursive: true });
      }

      // 保存详细日志（JSONL格式）
      const qualityLogFile = join(qualityDir, 'kline-quality.jsonl');
      appendFileSync(qualityLogFile, JSON.stringify(log) + '\n');

      // 生成可读报告（仅在有问题时）
      if (log.validation.errors.length > 0 || log.validation.warnings.length > 0) {
        const reportFile = join(
          qualityDir,
          `kline-quality-${log.symbol}-${Date.now()}.txt`
        );
        const report = generateQualityReport(log);
        writeFileSync(reportFile, report);
      }
    }

    // 2. 保存到数据库（异步，不阻塞主流程）
    saveToDatabase(log).catch((error) => {
      console.error('保存质量数据到数据库失败:', error);
    });

    // 3. 控制台输出（仅在质量较差时）
    if (log.metrics.overall < 0.9) {
      console.warn(
        `⚠️  K线数据质量告警 [${log.symbol}]: 综合评分 ${(log.metrics.overall * 100).toFixed(1)}%`
      );
      console.warn(
        `   完整性: ${(log.metrics.completeness * 100).toFixed(1)}%, 一致性: ${(log.metrics.consistency * 100).toFixed(1)}%, 准确性: ${(log.metrics.accuracy * 100).toFixed(1)}%`
      );
      console.warn(
        `   错误: ${log.validation.errors.length}, 告警: ${log.validation.warnings.length}, 清洗: ${log.cleaning.removed}条移除, ${log.cleaning.fixed}条修复`
      );
    }
  } catch (error) {
    // 日志记录失败不应影响主流程
    console.error('记录数据质量日志失败:', error);
  }
}

/**
 * 保存质量数据到数据库（异步）
 */
async function saveToDatabase(log: QualityLog): Promise<void> {
  const V2_API_BASE = process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001';

  try {
    // 转换为API需要的格式
    const payload = {
      symbol: log.symbol,
      period: log.period,
      start_date: log.requestedRange.startDate,
      end_date: log.requestedRange.endDate,
      limit: log.requestedRange.limit,
      original_count: log.metrics.totalRecords,
      cleaned_count: log.metrics.validRecords,
      removed_count: log.cleaning.removed,
      fixed_count: log.cleaning.fixed,
      error_count: log.validation.errors.length,
      warning_count: log.validation.warnings.length,
      errors: log.validation.errors.slice(0, 50), // 限制数量
      warnings: log.validation.warnings.slice(0, 50), // 限制数量
      cleaning_operations: log.cleaning.operations.slice(0, 50), // 限制数量
      completeness_score: log.metrics.completeness * 100,
      consistency_score: log.metrics.consistency * 100,
      accuracy_score: log.metrics.accuracy * 100,
      overall_score: log.metrics.overall * 100,
      grade: getQualityGrade(log.metrics.overall),
      duration_ms: log.durationMs,
    };

    const response = await fetch(`${V2_API_BASE}/api/data/quality-submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000), // 5秒超时
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      console.warn(`保存质量数据到数据库失败: HTTP ${response.status} ${errorText}`);
    }
  } catch (error) {
    // 静默失败，不影响主流程
    if (error instanceof Error && !error.message.includes('fetch failed')) {
      console.warn('保存质量数据到数据库失败:', error.message);
    }
  }
}

/**
 * 生成可读的质量报告
 */
function generateQualityReport(log: QualityLog): string {
  const lines: string[] = [];

  lines.push('═══════════════════════════════════════════════════════════');
  lines.push(`K线数据质量报告`);
  lines.push('═══════════════════════════════════════════════════════════');
  lines.push('');
  lines.push(`股票代码: ${log.symbol}`);
  lines.push(`数据周期: ${log.period}`);
  lines.push(`时间范围: ${log.requestedRange.startDate || '未指定'} ~ ${log.requestedRange.endDate || '未指定'}`);
  lines.push(`查询时间: ${log.timestamp}`);
  lines.push(`处理耗时: ${log.durationMs}ms`);
  lines.push('');

  lines.push('─── 质量指标 ───────────────────────────────────────────');
  lines.push(`总记录数: ${log.metrics.totalRecords}`);
  lines.push(`有效记录: ${log.metrics.validRecords} (${(log.metrics.completeness * 100).toFixed(1)}%)`);
  lines.push(`无效记录: ${log.metrics.invalidRecords}`);
  lines.push(`完整性: ${(log.metrics.completeness * 100).toFixed(1)}%`);
  lines.push(`一致性: ${(log.metrics.consistency * 100).toFixed(1)}%`);
  lines.push(`准确性: ${(log.metrics.accuracy * 100).toFixed(1)}%`);
  lines.push(`综合评分: ${(log.metrics.overall * 100).toFixed(1)}%`);
  lines.push('');

  if (log.validation.errors.length > 0) {
    lines.push('─── 验证错误 ───────────────────────────────────────────');
    log.validation.errors.slice(0, 20).forEach((error, i) => {
      lines.push(
        `${i + 1}. [${error.type}] ${error.message} ${error.index !== undefined ? `(索引: ${error.index})` : ''}`
      );
    });
    if (log.validation.errors.length > 20) {
      lines.push(`... 还有 ${log.validation.errors.length - 20} 个错误`);
    }
    lines.push('');
  }

  if (log.validation.warnings.length > 0) {
    lines.push('─── 验证告警 ───────────────────────────────────────────');
    log.validation.warnings.slice(0, 20).forEach((warning, i) => {
      lines.push(
        `${i + 1}. [${warning.type}] ${warning.message} ${warning.index !== undefined ? `(索引: ${warning.index})` : ''}`
      );
    });
    if (log.validation.warnings.length > 20) {
      lines.push(`... 还有 ${log.validation.warnings.length - 20} 个告警`);
    }
    lines.push('');
  }

  if (log.cleaning.operations.length > 0) {
    lines.push('─── 清洗操作 ───────────────────────────────────────────');
    lines.push(`移除: ${log.cleaning.removed}条, 修复: ${log.cleaning.fixed}条`);
    log.cleaning.operations.slice(0, 10).forEach((op, i) => {
      lines.push(`${i + 1}. [${op.type}] ${op.reason} (索引: ${op.index})`);
    });
    if (log.cleaning.operations.length > 10) {
      lines.push(`... 还有 ${log.cleaning.operations.length - 10} 个操作`);
    }
    lines.push('');
  }

  lines.push('═══════════════════════════════════════════════════════════');

  return lines.join('\n');
}

/**
 * 获取质量评级
 */
export function getQualityGrade(overall: number): string {
  if (overall >= 0.95) return 'A+ (优秀)';
  if (overall >= 0.9) return 'A (良好)';
  if (overall >= 0.8) return 'B (合格)';
  if (overall >= 0.7) return 'C (一般)';
  return 'D (较差)';
}
