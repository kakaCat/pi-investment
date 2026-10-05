/**
 * Memory Provider Port 测试
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { AgentOSMemoryProvider } from './agent-os-provider.js';
import { FileFallbackProvider } from './file-fallback.js';
import { initMemoryProvider, getMemoryProvider, resetMemoryProvider } from './provider-manager.js';
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

  describe('AgentOSMemoryProvider', () => {
    it('should initialize with session context', async () => {
      const provider = new AgentOSMemoryProvider();
      await provider.initialize('test-session', {
        sessionKind: 'user',
        channel: 'terminal',
      });

      expect(provider.name).toBe('agent-os');
      expect(provider.isAvailable()).toBe(true);
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
      expect(provider.name).toMatch(/agent-os|file-fallback/);

      const retrieved = getMemoryProvider();
      expect(retrieved).toBe(provider);
    });

    it('should fallback to file provider when agent-os unavailable', async () => {
      const provider = await initMemoryProvider({
        sessionId: 'test-session',
        sessionKind: 'user',
        channel: 'terminal',
        piDir: tempDir,
        forceFallback: true,
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

  // 2026-10-05 · REQ-261004202231-bb99：原 describe('Provenance') 用例对 V2MemoryProvider 的
  // 私有 _write 打桩，而 v2 客户端已随记忆子系统删除 → 该用例随之移除。
  // agent-os provider 的 provenance 由 agentOSMemoryWrite 的 metadata 承载（见 agent-os-provider）。
});
