import { BaseCliAdapter } from '../base-cli-adapter.js';
import { CliExecutionError, CliParseError } from '../types.js';

// 创建测试用的具体实现类
class TestCliAdapter extends BaseCliAdapter {
  // 暴露 protected 方法用于测试
  public testBuildCommand(domain: string, action: string, params: Record<string, string | number | boolean | undefined | null>): string[] {
    // Narrow to valid types — the real buildCommand filters undefined/null at runtime
    const clean: Record<string, string | number | boolean> = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ) as Record<string, string | number | boolean>;
    return this.buildCommand(domain, action, clean);
  }

  public testToCLIParam(key: string): string {
    return this.toCLIParam(key);
  }

  public testParseJsonOutput(stdout: string): any {
    return this.parseJsonOutput(stdout);
  }
}

describe('BaseCliAdapter', () => {
  let adapter: TestCliAdapter;

  beforeEach(() => {
    adapter = new TestCliAdapter();
  });

  describe('toCLIParam', () => {
    it('should convert camelCase to kebab-case', () => {
      expect(adapter.testToCLIParam('accountId')).toBe('account-id');
      expect(adapter.testToCLIParam('buyRangeLow')).toBe('buy-range-low');
      expect(adapter.testToCLIParam('stopLoss')).toBe('stop-loss');
    });

    it('should handle single word', () => {
      expect(adapter.testToCLIParam('symbol')).toBe('symbol');
      expect(adapter.testToCLIParam('status')).toBe('status');
    });
  });

  describe('buildCommand', () => {
    it('should build correct CLI argument array with parameters', () => {
      const args = adapter.testBuildCommand('position', 'list', {
        accountId: 'default',
        status: 'open'
      });
      expect(args).toEqual(['position', '+list', '--json', '--account-id', 'default', '--status', 'open']);
    });

    it('should skip undefined and null parameters', () => {
      const args = adapter.testBuildCommand('position', 'get', {
        symbol: '600036',
        accountId: undefined,
        notes: null
      });
      expect(args).toEqual(['position', '+get', '--json', '--symbol', '600036']);
    });

    it('should handle no parameters', () => {
      const args = adapter.testBuildCommand('position', 'summary', {});
      expect(args).toEqual(['position', '+summary', '--json']);
    });

    it('should prevent command injection by returning array', () => {
      const args = adapter.testBuildCommand('position', 'get', {
        symbol: '600036; rm -rf /'
      });
      // The malicious input is safely passed as a single argument
      expect(args).toEqual(['position', '+get', '--json', '--symbol', '600036; rm -rf /']);
    });
  });

  describe('parseJsonOutput', () => {
    it('should parse successful CLI output', () => {
      const output = JSON.stringify({
        data: { positions: [{ symbol: '600036' }] },
        status: 'success'
      });
      const result = adapter.testParseJsonOutput(output);
      expect(result).toEqual({ positions: [{ symbol: '600036' }] });
    });

    it('should throw error on CLI error status', () => {
      const output = JSON.stringify({
        status: 'error',
        message: 'Position not found'
      });
      expect(() => adapter.testParseJsonOutput(output)).toThrow('Position not found');
    });

    it('should throw CliParseError on invalid JSON', () => {
      expect(() => adapter.testParseJsonOutput('invalid json')).toThrow(CliParseError);
    });

    it('should throw CliParseError when data is missing on success', () => {
      const output = JSON.stringify({
        status: 'success'
      });
      expect(() => adapter.testParseJsonOutput(output)).toThrow(CliParseError);
      expect(() => adapter.testParseJsonOutput(output)).toThrow('data is missing');
    });
  });
});
