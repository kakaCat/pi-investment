import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { execSync } from 'child_process';
import { existsSync, statSync } from 'fs';
import { quantsysV2LogsPrompt, type QuantsysV2LogsParams, type QuantsysV2LogsResult } from './prompt';

export interface QuantsysV2Config {
  projectRoot: string;
  logFile: string;
}

export class QuantsysV2LogsTool extends BaseTool<QuantsysV2LogsParams, QuantsysV2LogsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'quantsys_v2_logs',
    category: 'quantsys-v2-manager',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = quantsysV2LogsPrompt;

  // 频率限制状态
  private toolCallCounts: Array<number> = [];
  private readonly RATE_LIMIT = {
    maxCalls: 3,
    windowMs: 60000, // 1分钟
  };

  constructor(private config: QuantsysV2Config) {
    super();
  }

  protected validate(params: QuantsysV2LogsParams): ValidationResult {
    const errors: string[] = [];

    if (params.lines !== undefined) {
      if (!Number.isInteger(params.lines) || params.lines < 1 || params.lines > 1000) {
        errors.push('lines 必须是 1-1000 之间的整数');
      }
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    // 频率限制检查
    const now = Date.now();
    const recentCalls = this.toolCallCounts.filter(t => now - t < this.RATE_LIMIT.windowMs);

    if (recentCalls.length >= this.RATE_LIMIT.maxCalls) {
      const oldestCall = Math.min(...recentCalls);
      const waitMs = this.RATE_LIMIT.windowMs - (now - oldestCall);
      return {
        success: false,
        errorType: ErrorType.BUSINESS_REJECTION,
        issue: `频率限制：在 ${this.RATE_LIMIT.windowMs / 1000}s 内已调用 ${recentCalls.length} 次（上限 ${this.RATE_LIMIT.maxCalls}）。请等待 ${Math.ceil(waitMs / 1000)}s`,
      };
    }

    // 记录本次调用
    recentCalls.push(now);
    this.toolCallCounts = recentCalls;

    return { success: true };
  }

  protected async execute(
    params: QuantsysV2LogsParams,
    context: ToolContext
  ): Promise<QuantsysV2LogsResult> {
    const { projectRoot, logFile } = this.config;
    const logPath = `${projectRoot}/${logFile}`;

    if (!existsSync(logPath)) {
      throw new Error(`Log file not found: ${logPath}`);
    }

    const lines = params.lines || 50;

    // 检查文件最后修改时间（陈旧检测）
    const stats = statSync(logPath);
    const ageMs = Date.now() - stats.mtimeMs;
    const ageHours = ageMs / (1000 * 60 * 60);
    const isStale = ageHours > 24; // 超过24小时算陈旧

    let cmd = `tail -${lines} "${logPath}"`;
    if (params.grep) {
      cmd += ` | grep -i "${params.grep}"`;
    }

    const output = execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
    const logLines = output.split('\n').filter(l => l.trim()); // 过滤空行

    return {
      lines: logLines,
      total: logLines.length,
      _metadata: {
        log_file: logPath,
        last_modified: stats.mtime.toISOString(),
        age_hours: Math.round(ageHours * 10) / 10,
        is_stale: isStale,
        warning: isStale
          ? `⚠️ 日志文件已 ${Math.round(ageHours)} 小时未更新，可能配置错误或服务未运行`
          : '',
      },
    };
  }

  protected wrap(data: QuantsysV2LogsResult, _context: ToolContext): ToolResponse<QuantsysV2LogsResult> {
    return {
      success: true,
      data,
    };
  }
}
