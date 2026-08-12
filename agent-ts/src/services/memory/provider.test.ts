/**
 * Memory Provider Port 测试
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { V2MemoryProvider } from '../v2-client.js';
import { FileFallbackProvider } from '../file-fallback.js';
import { initMemoryProvider, getMemoryProvider, resetMemoryProvider } from '../provider-manager.js';
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

describe('MemoryProvider', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'memory-test-'));
    resetMemoryProvider();
  });

  afterEach(() => {
    if (tempDir) {
      rmSync(tempDir, { recursive: true, force: true });
    }
    resetMemoryProvider();
  });

  describe('V2MemoryProvider', () => {
    it('should initialize with session context', async () => {
      const provider = new V2MemoryProvider('http://127.0.0.1:5001');
      await provider.initialize('test-session', {
        sessionKind: 'user',
        channel: 'terminal',
      });

      expect(provider.name).toBe('v2-memory');
      expect(provider.isAvailable()).toBe(true);
    });

    it('should format recalled memory within budget', async () => {
      const provider = new V2MemoryProvider('http://127.0.0.1:5001');
      await provider.initialize('test-session', { sessionKind: 'user' });

      // Mock search response
      const mockSearch = jest.spyOn(provider as any, '_search');
      mockSearch.mockResolvedValue({
        items: [
          { id: 1, title: 'Test Memory', content: 'This is a test memory', score: 0.9 },
          { id: 2, title: 'Another Memory', content: 'Another test memory', score: 0.8 },
        ],
        total: 2,
      });

      const recalled = await provider.prefetch('test query', 'test-session', 3, 200);

      expect(recalled).toBeTruthy();
      expect(recalled.length).toBeLessThan(200);
      mockSearch.mockRestore();
    });
  });

  describe('FileFallbackProvider', () => {
    it('should initialize with local directory', async () => {
      const provider = new FileFallbackProvider(tempDir);
      await provider.initialize('test-session', {
        sessionKind: 'user',
        channel: 'terminal',
      });

      expect(provider.name).toBe('file-fallback');
      expect(provider.isAvailable()).toBe(true);
    });

    it('should return empty string for empty query', async () => {
      const provider = new FileFallbackProvider(tempDir);
      await provider.initialize('test-session', { sessionKind: 'user' });

      const recalled = await provider.prefetch('', 'test-session');
      expect(recalled).toBe('');
    });
  });

  describe('Provider Manager', () => {
    it('should initialize and return provider', async () => {
      const provider = await initMemoryProvider({
        sessionId: 'test-session',
        sessionKind: 'user',
        channel: 'terminal',
        piDir: tempDir,
      });

      expect(provider).toBeTruthy();
      expect(provider.name).toMatch(/v2-memory|file-fallback/);

      const retrieved = getMemoryProvider();
      expect(retrieved).toBe(provider);
    });

    it('should fallback to file provider when v2 unavailable', async () => {
      const provider = await initMemoryProvider({
        sessionId: 'test-session',
        sessionKind: 'user',
        channel: 'terminal',
        piDir: tempDir,
        v2BaseUrl: 'http://localhost:9999', // 不存在的端口
      });

      expect(provider.name).toBe('file-fallback');
    });
  });

  describe('Experience Integration', () => {
    it('should write experience through provider', async () => {
      const provider = new FileFallbackProvider(tempDir);
      await provider.initialize('test-session', { sessionKind: 'user' });

      const result = await provider.writeExperience({
        scenario: 'MACD金叉买入测试',
        conditions: ['MACD金叉', '成交量放大'],
        action: 'buy',
        total_cases: 10,
        win_rate: 0.7,
        avg_return: 5.2,
        recommendation: 'moderate',
        reason: '技术形态良好',
        confidence: 0.8,
      });

      expect(result.success).toBe(true);
      expect(result.message).toContain('Experience recorded');
    });

    it('should query experience through provider', async () => {
      const provider = new FileFallbackProvider(tempDir);
      await provider.initialize('test-session', { sessionKind: 'user' });

      // 先写入
      await provider.writeExperience({
        scenario: 'MACD金叉买入',
        conditions: ['MACD金叉'],
        action: 'buy',
        total_cases: 5,
        win_rate: 0.6,
        avg_return: 3.0,
        recommendation: 'moderate',
        reason: '历史表现稳定',
        confidence: 0.7,
      });

      // 再查询
      const result = await provider.queryExperience({
        scenario: 'MACD',
        limit: 5,
      });

      expect(result).toContain('MACD');
    });
  });

  describe('Provenance', () => {
    it('should include session metadata in writes', async () => {
      const provider = new V2MemoryProvider('http://127.0.0.1:5001');
      await provider.initialize('cron-session-123', {
        sessionKind: 'cron',
        channel: 'scheduler',
      });

      const mockWrite = jest.spyOn(provider as any, '_write');
      mockWrite.mockResolvedValue({ id: 1 });

      await provider.writeExperience({
        scenario: 'Test',
        conditions: [],
        action: 'buy',
        total_cases: 1,
        win_rate: 1.0,
        avg_return: 1.0,
        recommendation: 'moderate',
        reason: 'test',
        confidence: 0.5,
      });

      expect(mockWrite).toHaveBeenCalled();
      const call = mockWrite.mock.calls[0][0];
      expect(call.provenance).toEqual({
        session_kind: 'cron',
        channel: 'scheduler',
        session_id: 'cron-session-123',
      });

      mockWrite.mockRestore();
    });
  });
});
