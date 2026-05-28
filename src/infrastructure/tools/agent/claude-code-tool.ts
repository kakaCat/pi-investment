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
