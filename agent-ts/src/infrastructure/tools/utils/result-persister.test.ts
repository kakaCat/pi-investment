/**
 * 工具持久化系统快速测试
 *
 * 验证核心功能是否正常工作
 */

import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { promises as fs } from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import {
  ToolResultPersister,
  saveToolResult,
  cleanupOldResults,
  listToolResults,
} from './result-persister.js';
import { handleToolResponse, wrapToolExecution } from './tool-response-handler.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TEST_DIR = path.join(__dirname, '../../../../../.cache/tool-results-test');

describe('ToolResultPersister', () => {
  let persister: ToolResultPersister;

  beforeAll(async () => {
    persister = new ToolResultPersister(1); // 1 hour TTL
    await fs.mkdir(TEST_DIR, { recursive: true });
  });

  afterAll(async () => {
    // 清理测试目录
    try {
      await fs.rm(TEST_DIR, { recursive: true, force: true });
    } catch (error) {
      console.warn('清理测试目录失败:', error);
    }
  });

  it('应该成功保存结果到文件', async () => {
    const result = await persister.saveResult({
      toolName: 'test_tool',
      data: { foo: 'bar', items: [1, 2, 3] },
      metadata: { param1: 'value1' },
    });

    expect(result.success).toBe(true);
    expect(result.filePath).toContain('test_tool_');
    expect(result.filePath).toContain('.json');
    expect(result.message).toContain('数据已保存');

    // 验证文件存在
    const exists = await fs.access(result.filePath).then(() => true).catch(() => false);
    expect(exists).toBe(true);
  });

  it('应该正确生成数据摘要', async () => {
    const result = await persister.saveResult({
      toolName: 'test_tool',
      data: { items: new Array(100).fill(0) },
    });

    expect(result.summary).toContain('包含');
    expect(result.summary).toContain('100 项');
  });

  it('应该成功读取持久化的结果', async () => {
    const saveResult = await persister.saveResult({
      toolName: 'test_tool',
      data: { message: 'hello' },
    });

    const readResult = await persister.readResult(saveResult.filePath);
    expect(readResult.toolName).toBe('test_tool');
    expect((readResult as any).data).toEqual({ message: 'hello' });
  });

  it('应该列出所有结果', async () => {
    await persister.saveResult({
      toolName: 'tool1',
      data: { a: 1 },
    });

    await persister.saveResult({
      toolName: 'tool2',
      data: { b: 2 },
    });

    const list = await persister.listResults();
    expect(list.length).toBeGreaterThanOrEqual(2);
    expect(list.every((item: any) => item.fileName.endsWith('.json'))).toBe(true);
  });

  it('应该清理过期文件', async () => {
    // 创建一个文件
    const result = await persister.saveResult({
      toolName: 'old_tool',
      data: { old: true },
    });

    // 立即清理（maxAge = 0）
    await persister.cleanup(0);

    // 验证文件被删除
    const exists = await fs.access(result.filePath).then(() => true).catch(() => false);
    expect(exists).toBe(false);
  });
});

describe('handleToolResponse', () => {
  let persister: ToolResultPersister;

  beforeAll(async () => {
    persister = new ToolResultPersister(); // Use default 24 hours TTL
    await fs.mkdir(TEST_DIR, { recursive: true });
  });

  afterAll(async () => {
    try {
      await fs.rm(TEST_DIR, { recursive: true, force: true });
    } catch (error) {
      console.warn('清理测试目录失败:', error);
    }
  });

  it('小数据应该直接返回', async () => {
    const response = await handleToolResponse({
      toolName: 'small_data_tool',
      data: { value: 123 },
      threshold: 1024,
    });

    expect(((response.content[0] as any).text)).toContain('123');
    expect(((response.content[0] as any).text)).not.toContain('数据已保存');
  });

  it('大数据应该持久化', async () => {
    const largeData = {
      items: new Array(1000).fill({ name: 'item', value: 12345 }),
    };

    const response = await handleToolResponse({
      toolName: 'large_data_tool',
      data: largeData,
      threshold: 1024, // 1KB threshold
    });

    expect(((response.content[0] as any).text)).toContain('数据已保存');
    expect(((response.content[0] as any).text)).toContain('.json');
    expect(((response.content[0] as any).text)).toContain('Read');
  });

  it('应该使用自定义格式化函数', async () => {
    const response = await handleToolResponse({
      toolName: 'formatted_tool',
      data: { count: 10 },
      formatter: (data: any) => `总数: ${data.count}`,
      threshold: 1024,
    });

    expect(((response.content[0] as any).text)).toBe('总数: 10');
  });
});

describe('wrapToolExecution', () => {
  it('应该成功执行并返回格式化结果', async () => {
    const executor = wrapToolExecution(
      { toolName: 'test_wrapper', threshold: 1024 },
      async (params: { value: number }) => ({
        data: { result: params.value * 2 },
      })
    );

    const response = await executor('tool-call-id', { value: 5 });
    expect(((response.content[0] as any).text)).toContain('10');
  });

  it('应该捕获并格式化错误', async () => {
    const executor = wrapToolExecution(
      { toolName: 'error_wrapper' },
      async () => {
        throw new Error('模拟错误');
      }
    );

    const response = await executor('tool-call-id', {});
    expect(((response.content[0] as any).text)).toContain('执行失败');
    expect(((response.content[0] as any).text)).toContain('模拟错误');
  });
});

describe('便捷函数', () => {
  beforeAll(async () => {
    await fs.mkdir(TEST_DIR, { recursive: true });
  });

  afterAll(async () => {
    try {
      await fs.rm(TEST_DIR, { recursive: true, force: true });
    } catch (error) {
      console.warn('清理测试目录失败:', error);
    }
  });

  it('saveToolResult 应该正常工作', async () => {
    const result = await saveToolResult({
      toolName: 'convenience_test',
      data: { test: true },
    });

    expect(result.success).toBe(true);
  });

  it('listToolResults 应该正常工作', async () => {
    const list = await listToolResults();
    expect(Array.isArray(list)).toBe(true);
  });

  it('cleanupOldResults 应该正常工作', async () => {
    await expect(cleanupOldResults(24)).resolves.not.toThrow();
  });
});
