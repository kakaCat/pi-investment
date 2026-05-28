// src/infrastructure/tools/agent/claude-code-tool.test.ts
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { spawn } from 'child_process';
import { EventEmitter } from 'events';
import { claudeCodeTool } from './claude-code-tool.js';

// Mock child_process
jest.mock('child_process');

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
    mockProcess = new MockChildProcess();
    (spawn as jest.MockedFunction<typeof spawn>).mockReturnValue(mockProcess as any);

    // Set environment variables for testing
    process.env.CLAUDE_CODE_ENABLED = 'true';
    process.env.CLAUDE_CODE_CLI_PATH = 'claude-code';
    process.env.CLAUDE_CODE_TIMEOUT = '120000';
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // Tests will be added in next steps
});
