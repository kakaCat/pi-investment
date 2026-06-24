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
  CLI_PATH: process.env.CLAUDE_CODE_CLI_PATH || 'claude',
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
    let resolved = false;
    const safeResolve = (result: ClaudeCodeResult) => {
      if (!resolved) {
        resolved = true;
        resolve(result);
      }
    };

    const ctx: ExecutionContext = {
      process: null as any,
      stdout: '',
      stderr: '',
      startTime,
      timeoutHandle: undefined,
    };

    try {
      // Build prompt with task, context, and files
      let prompt = params.task;
      if (params.context) {
        prompt += `\n\nContext: ${params.context}`;
      }
      if (params.files && params.files.length > 0) {
        prompt += `\n\nRelevant files: ${params.files.join(', ')}`;
      }

      // Spawn Claude Code process with correct arguments
      const args: string[] = [
        '-p',                          // Print mode (non-interactive)
        '--output-format', 'json',     // JSON output
        '--bare',                      // Minimal mode (skip hooks, LSP, etc.)
        prompt,                        // The prompt as argument
      ];

      ctx.process = spawn(CONFIG.CLI_PATH, args, {
        cwd: PROJECT_ROOT,
        stdio: ['ignore', 'pipe', 'pipe'],  // No stdin needed
        env: { ...process.env },
      });

      // Set up timeout
      ctx.timeoutHandle = setTimeout(() => {
        ctx.process.kill('SIGTERM');
        safeResolve({
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
          safeResolve({
            success: true,
            output: ctx.stdout,
            execution_time: executionTime,
          });
        } else {
          safeResolve({
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
          safeResolve({
            success: false,
            output: '',
            execution_time: executionTime,
            error: 'Claude Code CLI not found in PATH',
          });
        } else if ((error as any).code === 'EACCES') {
          safeResolve({
            success: false,
            output: '',
            execution_time: executionTime,
            error: 'Permission denied. Check Claude Code CLI permissions.',
          });
        } else {
          safeResolve({
            success: false,
            output: '',
            execution_time: executionTime,
            error: `Process error: ${error.message}`,
          });
        }
      });

    } catch (error) {
      if (ctx.timeoutHandle) {
        clearTimeout(ctx.timeoutHandle);
      }
      ctx.process?.kill();

      safeResolve({
        success: false,
        output: '',
        execution_time: Date.now() - startTime,
        error: `Execution failed: ${error instanceof Error ? error.message : String(error)}`,
      });
    }
  });
}

/**
 * Claude Code Tool Definition
 *
 * Delegates code-related tasks to Claude Code CLI for implementation,
 * review, analysis, and refactoring.
 */
export const claudeCodeTool: ToolDefinition = {
  name: 'claude_code',
  label: 'Claude Code 集成',
  description: 'Delegate code-related tasks to Claude Code for implementation, review, or analysis. Use for code review, refactoring, architecture analysis, bug fixing, and code generation.',
  parameters: Type.Object({
    task: Type.String({
      description: 'Task description for Claude Code (e.g., "Review this service for code quality")',
    }),
    context: Type.Optional(Type.String({
      description: 'Optional context information to help Claude Code understand the task',
    })),
    files: Type.Optional(Type.Array(Type.String(), {
      description: 'Relevant file paths for the task',
    })),
    timeout: Type.Optional(Type.Number({
      description: 'Timeout in milliseconds (default: 120000)',
      minimum: 10000,
      maximum: 600000,
    })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    // Check if tool is enabled
    if (!CONFIG.ENABLED) {
      return {
        content: [{
          type: "text" as const,
          text: 'Claude Code integration is disabled. Set CLAUDE_CODE_ENABLED=true to enable.',
        }],
        details: {
          enabled: false,
        },
      };
    }

    // Execute Claude Code
    const result = await executeClaudeCode(params as ClaudeCodeParams);

    // Format response
    let responseText = '';
    if ((result as any).success) {
      responseText = `✅ Claude Code execution completed (${result.execution_time}ms)\n\n${result.output}`;
    } else {
      responseText = `❌ Claude Code execution failed (${result.execution_time}ms)\n\nError: ${(result as any).error}\n\n${result.output ? `Output:\n${result.output}` : ''}`;
    }

    return {
      content: [{
        type: "text" as const,
        text: responseText,
      }],
      details: {
        success: result.success,
        execution_time: result.execution_time,
        files_modified: result.files_modified,
      },
    };
  },
};
