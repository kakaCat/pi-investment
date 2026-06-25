/**
 * Tool Result Wrapper
 *
 * Utility functions to wrap tool return values into AgentToolResult format
 * required by the pi-coding-agent SDK.
 */

import type { AgentToolResult } from "@mariozechner/pi-agent-core";

/**
 * Wrap a plain string or formatted output into AgentToolResult
 */
export function wrapToolResult(
  content: string,
  details?: unknown
): AgentToolResult<unknown> {
  return {
    content: [{ type: "text" as const, text: content }],
    details: details ?? {},
  };
}

/**
 * Wrap an error message into AgentToolResult
 */
export function wrapToolError(
  errorMessage: string,
  details?: unknown
): AgentToolResult<unknown> {
  return {
    content: [{ type: "text" as const, text: `❌ ${errorMessage}` }],
    details: details ?? {},
  };
}

/**
 * Type guard to check if a value is already an AgentToolResult
 */
export function isToolResult(value: unknown): value is AgentToolResult<unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    "content" in value &&
    Array.isArray((value as any).content)
  );
}

/**
 * Ensure a value is an AgentToolResult - wrap it if it's a string
 */
export function ensureToolResult(
  value: string | AgentToolResult<unknown>,
  details?: unknown
): AgentToolResult<unknown> {
  if (isToolResult(value)) {
    return value;
  }
  return wrapToolResult(value, details);
}
