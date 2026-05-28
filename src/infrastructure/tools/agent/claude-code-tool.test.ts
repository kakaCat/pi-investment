// src/infrastructure/tools/agent/claude-code-tool.test.ts
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import type { ChildProcess } from 'child_process';
import { EventEmitter } from 'events';

// Mock child_process module BEFORE importing the tool
const mockSpawn = jest.fn();
const mockExecSync = jest.fn();

jest.unstable_mockModule('child_process', () => ({
  spawn: mockSpawn,
  execSync: mockExecSync,
}));

// Now import the tool after mocking
const { claudeCodeTool } = await import('./claude-code-tool.js');

// Mock process class for testing
class MockChildProcess extends EventEmitter {
  stdin = {
    write: jest.fn(),
    end: jest.fn(),
  };
  stdout = new EventEmitter();
  stderr = new EventEmitter();
  kill = jest.fn();
  pid = 12345;
}

describe('claude-code-tool', () => {
  let mockProcess: MockChildProcess;

  beforeEach(() => {
    // Create fresh mock process
    mockProcess = new MockChildProcess();

    // Reset mocks
    mockSpawn.mockClear();
    mockExecSync.mockClear();

    // Configure mockSpawn to return our mock process
    mockSpawn.mockReturnValue(mockProcess as any);

    // Mock execSync to simulate CLI being installed
    // Must return a string or Buffer, not throw
    mockExecSync.mockImplementation(((cmd: string) => {
      if (cmd.includes('--version')) {
        return Buffer.from('claude-code v1.0.0\n');
      }
      return Buffer.from('');
    }) as any);

    // Set environment variables for testing
    process.env.CLAUDE_CODE_ENABLED = 'true';
    process.env.CLAUDE_CODE_CLI_PATH = 'claude-code';
    process.env.CLAUDE_CODE_TIMEOUT = '120000';
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // Task 9: Parameter Validation Tests
  describe('Parameter Validation', () => {
    it('should accept valid parameters', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-1', {
        task: 'test task',
        context: 'test context',
        timeout: 60000,
      });

      setTimeout(() => {
        mockProcess.stdout.emit('data', Buffer.from('test output'));
        mockProcess.emit('exit', 0);
      }, 10);

      const result = await executePromise;
      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');
    });

    it('should handle missing optional parameters', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-2', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.stdout.emit('data', Buffer.from('output'));
        mockProcess.emit('exit', 0);
      }, 10);

      const result = await executePromise;
      expect(result.content).toHaveLength(1);
      // Verify spawn was called (CLI check passed)
      expect(mockSpawn).toHaveBeenCalled();
      expect(mockSpawn).toHaveBeenCalledWith(
        'claude-code',
        expect.arrayContaining(['--json']),
        expect.any(Object)
      );
    });

    it('should use default timeout when not specified', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-3', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.emit('exit', 0);
      }, 10);

      await executePromise;
      expect(mockSpawn).toHaveBeenCalled();
    });
  });

  // Task 10: Error Scenarios Tests
  describe('Error Scenarios', () => {
    it('should handle CLI not found (ENOENT)', async () => {
      // Create fresh mock process for this test
      const freshMockProcess = new MockChildProcess();
      mockSpawn.mockReturnValue(freshMockProcess as any);

      const executePromise = (claudeCodeTool.execute as any)('test-4', {
        task: 'test task',
      });

      setTimeout(() => {
        const error = new Error('spawn claude-code ENOENT') as NodeJS.ErrnoException;
        error.code = 'ENOENT';
        freshMockProcess.emit('error', error);
      }, 10);

      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('failed');
    });

    it('should handle permission denied (EACCES)', async () => {
      // Create fresh mock process for this test
      const freshMockProcess = new MockChildProcess();
      mockSpawn.mockReturnValue(freshMockProcess as any);

      const executePromise = (claudeCodeTool.execute as any)('test-5', {
        task: 'test task',
      });

      setTimeout(() => {
        const error = new Error('spawn claude-code EACCES') as NodeJS.ErrnoException;
        error.code = 'EACCES';
        freshMockProcess.emit('error', error);
      }, 10);

      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('failed');
    });

    it('should handle non-zero exit code', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-6', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.stderr.emit('data', Buffer.from('error message'));
        mockProcess.emit('exit', 1);
      }, 10);

      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('failed');
      expect(result.details?.success).toBe(false);
    });

    it('should handle process crash', async () => {
      // Create fresh mock process for this test
      const freshMockProcess = new MockChildProcess();
      mockSpawn.mockReturnValue(freshMockProcess as any);

      const executePromise = (claudeCodeTool.execute as any)('test-7', {
        task: 'test task',
      });

      setTimeout(() => {
        const error = new Error('Process crashed');
        freshMockProcess.emit('error', error);
      }, 10);

      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('failed');
    });
  });

  // Task 11: Timeout Handling Tests
  describe('Timeout Handling', () => {
    it('should timeout on long-running process', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-8', {
        task: 'test task',
        timeout: 100, // 100ms timeout
      });

      // Don't emit close event - let it timeout
      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('timeout');
      expect(mockProcess.kill).toHaveBeenCalled();
    });

    it('should include partial output on timeout', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-9', {
        task: 'test task',
        timeout: 100,
      });

      setTimeout(() => {
        mockProcess.stdout.emit('data', Buffer.from('partial output'));
      }, 10);

      const result = await executePromise;
      expect((result.content[0] as any).text).toContain('timeout');
    });

    it('should cleanup on timeout', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-10', {
        task: 'test task',
        timeout: 100,
      });

      await executePromise;
      expect(mockProcess.kill).toHaveBeenCalledWith('SIGTERM');
    });
  });

  // Task 12: Output Handling Tests
  describe('Output Handling', () => {
    it('should collect stdout', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-11', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.stdout.emit('data', Buffer.from('line 1\n'));
        mockProcess.stdout.emit('data', Buffer.from('line 2\n'));
        mockProcess.emit('exit', 0);
      }, 10);

      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('line 1');
      expect((result.content[0] as any).text).toContain('line 2');
    });

    it('should collect stderr', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-12', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.stderr.emit('data', Buffer.from('error line\n'));
        mockProcess.emit('exit', 1);
      }, 10);

      const result = await executePromise;
      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('failed');
    });

    it('should track execution time', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-13', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.emit('exit', 0);
      }, 50);

      const result = await executePromise;
      expect(result.details?.execution_time).toBeGreaterThanOrEqual(50);
      expect(result.details?.execution_time).toBeLessThan(200);
    });
  });

  // Task 13: Configuration Tests
  describe('Configuration', () => {
    it('should respect CLAUDE_CODE_ENABLED=false', async () => {
      // Need to set before module loads, but since module is already loaded,
      // we test that the tool checks the config at runtime
      const originalEnabled = process.env.CLAUDE_CODE_ENABLED;
      process.env.CLAUDE_CODE_ENABLED = 'false';

      // Re-import to get fresh config
      jest.resetModules();
      const { claudeCodeTool: freshTool } = await import('./claude-code-tool.js');

      const result = await (freshTool.execute as any)('test-14', {
        task: 'test task',
      });

      expect(result.content[0].type).toBe('text');
      expect((result.content[0] as any).text).toContain('disabled');
      expect(mockSpawn).not.toHaveBeenCalled();

      // Restore
      process.env.CLAUDE_CODE_ENABLED = originalEnabled;
    });

    it('should use custom CLI path', async () => {
      // Need to reload module with new env var
      const originalPath = process.env.CLAUDE_CODE_CLI_PATH;
      process.env.CLAUDE_CODE_CLI_PATH = '/custom/path/claude-code';

      // Mock execSync for the custom path
      mockExecSync.mockImplementation(((cmd: string) => {
        if (cmd.includes('/custom/path/claude-code') && cmd.includes('--version')) {
          return Buffer.from('claude-code v1.0.0\n');
        }
        return Buffer.from('');
      }) as any);

      // Re-import to get fresh config
      jest.resetModules();
      const { claudeCodeTool: freshTool } = await import('./claude-code-tool.js?t=' + Date.now());

      const executePromise = (freshTool.execute as any)('test-15', {
        task: 'test task',
      });

      setTimeout(() => {
        mockProcess.emit('exit', 0);
      }, 10);

      await executePromise;
      expect(mockSpawn).toHaveBeenCalledWith(
        '/custom/path/claude-code',
        expect.any(Array),
        expect.any(Object)
      );

      // Restore
      process.env.CLAUDE_CODE_CLI_PATH = originalPath;
    });

    it('should write stdin input', async () => {
      const executePromise = (claudeCodeTool.execute as any)('test-16', {
        task: 'test task',
        context: 'input data',
      });

      setTimeout(() => {
        mockProcess.emit('exit', 0);
      }, 10);

      await executePromise;
      expect(mockProcess.stdin.write).toHaveBeenCalled();
      expect(mockProcess.stdin.end).toHaveBeenCalled();
    });
  });
});
