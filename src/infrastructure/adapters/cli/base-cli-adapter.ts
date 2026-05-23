import { execFile } from 'child_process';
import { promisify } from 'util';
import { CliExecutionError, CliParseError } from './types.js';

const execFileAsync = promisify(execFile);

export abstract class BaseCliAdapter {
  private readonly cliPath: string;
  private readonly timeout: number;
  private readonly maxBuffer: number;

  constructor(config?: {
    cliPath?: string;
    timeout?: number;
    maxBuffer?: number;
  }) {
    this.cliPath = config?.cliPath || 'quant';
    this.timeout = config?.timeout || 30000;  // 30 seconds
    this.maxBuffer = config?.maxBuffer || 10 * 1024 * 1024;  // 10MB
  }

  /**
   * 执行 CLI 命令
   */
  protected async executeCommand(
    domain: string,
    action: string,
    params: Record<string, string | number | boolean>
  ): Promise<any> {
    const args = this.buildCommand(domain, action, params);
    const commandStr = `${this.cliPath} ${args.join(' ')}`;

    try {
      const { stdout, stderr } = await execFileAsync(this.cliPath, args, {
        timeout: this.timeout,
        maxBuffer: this.maxBuffer
      });

      // Check stderr for actual errors (non-empty and contains error indicators)
      if (stderr && /error|exception|failed/i.test(stderr)) {
        console.error(`CLI stderr: ${stderr}`);
        throw new Error(`CLI command failed: ${stderr}`);
      } else if (stderr) {
        console.warn(`CLI stderr: ${stderr}`);
      }

      return this.parseJsonOutput(stdout);
    } catch (error: any) {
      throw this.handleError(error, commandStr);
    }
  }

  /**
   * 构建 CLI 命令参数数组
   */
  protected buildCommand(
    domain: string,
    action: string,
    params: Record<string, string | number | boolean>
  ): string[] {
    const args = [domain, `+${action}`, '--json'];

    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        const cliKey = this.toCLIParam(key);
        args.push(`--${cliKey}`, String(value));
      }
    }

    return args;
  }

  /**
   * 将 camelCase 转换为 kebab-case
   */
  protected toCLIParam(key: string): string {
    return key.replace(/([A-Z])/g, '-$1').toLowerCase();
  }

  /**
   * 解析 CLI JSON 输出
   */
  protected parseJsonOutput(stdout: string): any {
    try {
      const parsed = JSON.parse(stdout);

      // CLI 返回格式：{ "data": {...}, "status": "success" }
      if (parsed.status === 'error') {
        throw new Error(parsed.message || 'CLI command failed');
      }

      // Validate that data exists when status is success
      if (parsed.status === 'success' && parsed.data === undefined) {
        throw new CliParseError('CLI returned success but data is missing', stdout);
      }

      return parsed.data;
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        throw new CliParseError('Failed to parse CLI JSON output', stdout);
      }
      throw error;
    }
  }

  /**
   * 处理错误
   */
  protected handleError(error: any, command: string): never {
    if (error.killed || error.signal === 'SIGTERM') {
      throw new CliExecutionError('Command timeout', command, -1);
    }

    if (error.code) {
      throw new CliExecutionError(
        error.message || 'Command execution failed',
        command,
        error.code
      );
    }

    throw error;
  }
}
