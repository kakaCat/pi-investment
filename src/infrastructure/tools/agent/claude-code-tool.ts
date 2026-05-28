// src/infrastructure/tools/agent/claude-code-tool.ts
import { spawn, execSync, type ChildProcess } from 'child_process';
import { Type } from '@sinclair/typebox';
import type { ToolDefinition } from '../index.js';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Parameters for Claude Code tool invocation
 */
interface ClaudeCodeParams {
  task: string;           // Task description for Claude Code
  context?: string;       // Optional context information
  files?: string[];       // Relevant file paths
  timeout?: number;       // Timeout in milliseconds (default: 120000)
}

/**
 * Result returned from Claude Code execution
 */
interface ClaudeCodeResult {
  success: boolean;
  output: string;              // Claude Code's output
  files_modified?: string[];   // List of modified files
  execution_time: number;      // Execution time in milliseconds
  error?: string;              // Error message if failed
}

/**
 * Internal execution context
 */
interface ExecutionContext {
  process: ChildProcess;
  stdout: string;
  stderr: string;
  startTime: number;
  timeoutHandle?: NodeJS.Timeout;
}

/**
 * Configuration loaded from environment variables
 */
const CONFIG = {
  CLI_PATH: process.env.CLAUDE_CODE_CLI_PATH || 'claude-code',
  DEFAULT_TIMEOUT: Math.max(1000, parseInt(process.env.CLAUDE_CODE_TIMEOUT || '120000', 10) || 120000),
  ENABLED: process.env.CLAUDE_CODE_ENABLED !== 'false',
} as const;

/**
 * Find project root directory
 */
function findProjectRoot(startDir: string = __dirname): string {
  let current = startDir;
  const maxDepth = 20;
  let depth = 0;

  while (depth < maxDepth) {
    if (
      existsSync(join(current, 'package.json')) &&
      existsSync(join(current, 'src'))
    ) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      // Reached filesystem root
      throw new Error(`Could not find project root from ${startDir}`);
    }
    current = parent;
    depth++;
  }

  throw new Error(`Exceeded max depth (${maxDepth}) searching for project root from ${startDir}`);
}

const PROJECT_ROOT = findProjectRoot();

/**
 * Check if Claude Code CLI is installed and accessible
 */
function checkClaudeCodeInstalled(): boolean {
  try {
    execSync(`${CONFIG.CLI_PATH} --version`, {
      stdio: 'pipe',
      timeout: 5000,
    });
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Get Claude Code CLI version
 */
function getClaudeCodeVersion(): string | null {
  try {
    const output = execSync(`${CONFIG.CLI_PATH} --version`, {
      encoding: 'utf-8',
      stdio: 'pipe',
      timeout: 5000,
    });
    return output.trim();
  } catch (error) {
    return null;
  }
}

/**
 * Check all prerequisites and return status
 */
function checkPrerequisites(): {
  installed: boolean;
  version: string | null;
  error?: string;
} {
  const installed = checkClaudeCodeInstalled();

  if (!installed) {
    return {
      installed: false,
      version: null,
      error: 'Claude Code CLI not found. Please install it first.',
    };
  }

  const version = getClaudeCodeVersion();

  return {
    installed: true,
    version,
  };
}

/**
 * Execute Claude Code CLI with given parameters
 */
async function executeClaudeCode(params: ClaudeCodeParams): Promise<ClaudeCodeResult> {
  const startTime = Date.now();
  const timeoutMs = params.timeout || CONFIG.DEFAULT_TIMEOUT;

  // Check prerequisites first
  const prereqs = checkPrerequisites();
  if (!prereqs.installed) {
    return {
      success: false,
      output: '',
      execution_time: Date.now() - startTime,
      error: prereqs.error || 'Claude Code CLI not available',
    };
  }

  return new Promise((resolve) => {
    const ctx: ExecutionContext = {
      process: null as any,
      stdout: '',
      stderr: '',
      startTime,
      timeoutHandle: undefined,
    };

    try {
      // Spawn Claude Code process
      const args: string[] = [];

      ctx.process = spawn(CONFIG.CLI_PATH, args, {
        cwd: PROJECT_ROOT,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env },
      });

      // Set up timeout
      ctx.timeoutHandle = setTimeout(() => {
        ctx.process.kill('SIGTERM');
        resolve({
          success: false,
          output: ctx.stdout,
          execution_time: Date.now() - startTime,
          error: `Execution timeout after ${timeoutMs}ms`,
        });
      }, timeoutMs);

      // Collect stdout
      ctx.process.stdout?.on('data', (chunk: Buffer) => {
        ctx.stdout += chunk.toString();
      });

      // Collect stderr
      ctx.process.stderr?.on('data', (chunk: Buffer) => {
        ctx.stderr += chunk.toString();
      });

      // Handle process exit
      ctx.process.on('exit', (code: number | null) => {
        if (ctx.timeoutHandle) {
          clearTimeout(ctx.timeoutHandle);
        }

        const executionTime = Date.now() - startTime;

        if (code === 0) {
          resolve({
            success: true,
            output: ctx.stdout,
            execution_time: executionTime,
          });
        } else {
          resolve({
            success: false,
            output: ctx.stdout,
            execution_time: executionTime,
            error: `Process exited with code ${code}. stderr: ${ctx.stderr}`,
          });
        }
      });

      // Handle process errors
      ctx.process.on('error', (error: Error) => {
        if (ctx.timeoutHandle) {
          clearTimeout(ctx.timeoutHandle);
        }

        const executionTime = Date.now() - startTime;

        if ((error as any).code === 'ENOENT') {
          resolve({
            success: false,
            output: '',
            execution_time: executionTime,
            error: 'Claude Code CLI not found in PATH',
          });
        } else if ((error as any).code === 'EACCES') {
          resolve({
            success: false,
            output: '',
            execution_time: executionTime,
            error: 'Permission denied. Check Claude Code CLI permissions.',
          });
        } else {
          resolve({
            success: false,
            output: '',
            execution_time: executionTime,
            error: `Process error: ${error.message}`,
          });
        }
      });

      // Write input to stdin
      const input = JSON.stringify({
        task: params.task,
        context: params.context,
        files: params.files,
      });

      ctx.process.stdin?.write(input);
      ctx.process.stdin?.end();

    } catch (error) {
      if (ctx.timeoutHandle) {
        clearTimeout(ctx.timeoutHandle);
      }

      resolve({
        success: false,
        output: '',
        execution_time: Date.now() - startTime,
        error: `Execution failed: ${error instanceof Error ? error.message : String(error)}`,
      });
    }
  });
}
