/**
 * 错误格式化工具
 *
 * 将 ValidationResult 转换为 LLM 友好的错误消息
 */

import { ValidationResult } from '@pi-investment/core-tool';

/**
 * 格式化错误信息为 LLM 友好的文本
 */
export function formatErrorMessage(error: ValidationResult): string {
  const parts: string[] = [];

  // 问题描述
  if (error.issue) {
    parts.push(`❌ ${error.issue}`);
  }

  // 接收值与期望值对比
  if (error.received !== undefined && error.expected) {
    parts.push(`\n接收到: ${JSON.stringify(error.received)}`);
    parts.push(`期望格式: ${error.expected}`);
  }

  // 示例
  if (error.example) {
    parts.push(`\n正确示例: ${JSON.stringify(error.example)}`);
  }

  // 引导说明
  if (error.guide) {
    parts.push(`\n💡 ${error.guide}`);
  }

  // 常见错误
  if (error.commonMistakes && error.commonMistakes.length > 0) {
    parts.push('\n⚠️  常见错误:');
    error.commonMistakes.forEach((mistake) => {
      parts.push(`  - ${mistake}`);
    });
  }

  // 可能原因
  if (error.possibleReasons && error.possibleReasons.length > 0) {
    parts.push('\n🔍 可能原因:');
    error.possibleReasons.forEach((reason) => {
      parts.push(`  - ${reason}`);
    });
  }

  // 解决方案
  if (error.solutions && error.solutions.length > 0) {
    parts.push('\n🔧 解决方案:');
    error.solutions.forEach((solution, i) => {
      parts.push(`  ${i + 1}. ${solution.description}`);
      if (solution.example) {
        parts.push(`     示例: ${solution.example}`);
      }
    });
  }

  // 替代方案
  if (error.alternatives && error.alternatives.length > 0) {
    parts.push('\n🔄 替代方案:');
    error.alternatives.forEach((alt, i) => {
      parts.push(`  ${i + 1}. ${alt.reason}`);
      if (alt.example) {
        parts.push(`     示例: ${alt.example}`);
      }
    });
  }

  return parts.join('\n');
}

/**
 * 格式化错误信息为简洁版本（仅包含核心信息）
 */
export function formatErrorMessageBrief(error: ValidationResult): string {
  const parts: string[] = [];

  if (error.issue) {
    parts.push(error.issue);
  }

  if (error.guide) {
    parts.push(error.guide);
  }

  if (error.example) {
    parts.push(`示例: ${JSON.stringify(error.example)}`);
  }

  return parts.join('\n');
}
