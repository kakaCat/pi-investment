/**
 * Shared test utilities for tool tests
 */

/**
 * Extract text content from tool execution result
 */
export function getResponseText(result: any): string {
  return result.content[0].text;
}
