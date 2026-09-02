/**
 * WeeklyReportTool - M6 学习飞轮周报工具
 *
 * 封装后端 GET /api/reports/weekly（json/markdown 双格式），
 * 供 weekly-report-m6 定时任务/复盘场景生成学习飞轮周报。
 * 修复 2026-09-03：agent 侧原无 weekly_report 工具，prompt 引用断裂 → 业务空转。
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { weeklyReportPrompt, WeeklyReportParams, WeeklyReportResult } from './prompt';

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * 周报工具类
 */
export class WeeklyReportTool extends BaseTool<WeeklyReportParams, WeeklyReportResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'weekly_report',
    category: 'evolver',
    version: '1.0.0',
    timeoutMs: 60000, // 后端生成周报可能较慢
  };

  protected readonly prompt = weeklyReportPrompt;

  constructor(private baseURL: string) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(params: WeeklyReportParams): ValidationResult {
    if (params.week_start !== undefined && params.week_start !== null) {
      if (typeof params.week_start !== 'string' || !DATE_RE.test(params.week_start)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'week_start',
          issue: 'week_start 须为 YYYY-MM-DD 格式',
          received: params.week_start,
          expected: 'YYYY-MM-DD',
        };
      }
    }
    if (params.week_end !== undefined && params.week_end !== null) {
      if (typeof params.week_end !== 'string' || !DATE_RE.test(params.week_end)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'week_end',
          issue: 'week_end 须为 YYYY-MM-DD 格式',
          received: params.week_end,
          expected: 'YYYY-MM-DD',
        };
      }
    }
    if (params.format !== undefined && params.format !== 'json' && params.format !== 'markdown') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'format',
        issue: 'format 只能是 json 或 markdown',
        received: params.format,
        expected: 'json | markdown',
      };
    }
    return { success: true };
  }

  /**
   * Phase 2: 执行——调用后端生成周报（json + markdown 双取）
   */
  protected async execute(params: WeeklyReportParams, _context: ToolContext): Promise<WeeklyReportResult> {
    const base = `${this.baseURL.replace(/\/$/, '')}`;
    const qs: string[] = [];
    if (params.week_start) qs.push(`week_start=${encodeURIComponent(params.week_start)}`);
    if (params.week_end) qs.push(`week_end=${encodeURIComponent(params.week_end)}`);

    // 1. 拉结构化数据
    const dataUrl = `${base}/api/reports/weekly${qs.length ? '?' + qs.join('&') : ''}`;
    const dataResp = await fetch(dataUrl);
    if (!dataResp.ok) {
      throw new Error(`周报数据获取失败: HTTP ${dataResp.status}`);
    }
    const dataBody: any = await dataResp.json();
    if (!dataBody?.success) {
      throw new Error(dataBody?.message || '周报数据获取失败（后端未返回 success）');
    }
    const report: any = dataBody.data || {};

    // 2. 拉 markdown 全文
    const mdQs = [...qs, 'format=markdown'];
    const mdUrl = `${base}/api/reports/weekly?${mdQs.join('&')}`;
    const mdResp = await fetch(mdUrl);
    let markdown = '';
    if (mdResp.ok) {
      const mdBody: any = await mdResp.json();
      markdown = mdBody?.data?.content || '';
    }

    return {
      period: report.period || { start: '', end: '', weekNum: 0, year: 0 },
      summary: report.summary || {},
      signals: report.signals || {},
      attribution: report.attribution || {},
      regimeChanges: report.regimeChanges || [],
      highlights: report.highlights || [],
      recommendations: report.recommendations || [],
      markdown,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: WeeklyReportResult, _context: ToolContext): ToolResponse<WeeklyReportResult> {
    return {
      success: true,
      data: result,
    };
  }
}
