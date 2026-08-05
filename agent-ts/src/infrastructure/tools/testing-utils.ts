/**
 * 测试共享工具
 */

/** 从工具结果提取文本（content[0].text） */
export function getResponseText(result: any): string {
  return (result.content[0] as any).text;
}
