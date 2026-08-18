import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createEvolutionStatusTool } from '../src/tools/evolution-status-tool.js';
import { createWatchListTool } from '../src/tools/watch-list-tool.js';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

describe('Intelligence Tools', () => {
  let mockClient: AgentDHClient;

  beforeEach(() => {
    mockClient = {
      quantsysV2: {
        listWatchRules: vi.fn(),
      },
    } as any;
  });

  describe('evolution-status-tool', () => {
    it('should have correct metadata', () => {
      const tool = createEvolutionStatusTool(mockClient);
      expect(tool.name).toBe('evolution_status');
      expect(tool.description).toContain('进化状态');
    });

    it('should return blocked status', async () => {
      const tool = createEvolutionStatusTool(mockClient);
      const result = await tool.execute({}, { signal: new AbortController().signal } as any);

      expect(result).toHaveProperty('error');
      expect(result).toHaveProperty('status', 'blocked');
      expect(result).toHaveProperty('reason');
    });
  });

  describe('watch-list-tool', () => {
    it('should have correct metadata', () => {
      const tool = createWatchListTool(mockClient);
      expect(tool.name).toBe('watch_list');
      expect(tool.description).toContain('盯盘规则');
    });

    it('should call listWatchRules', async () => {
      const mockRules = [
        { id: 1, name: 'Price Alert', symbol: '600519', condition: 'price > 2000', enabled: true, created_at: '2024-01-01', updated_at: '2024-01-01' },
      ];
      vi.mocked(mockClient.quantsysV2.listWatchRules).mockResolvedValue(mockRules);

      const tool = createWatchListTool(mockClient);
      const result = await tool.execute({}, { signal: new AbortController().signal } as any);

      expect(mockClient.quantsysV2.listWatchRules).toHaveBeenCalled();
      expect(result).toEqual(mockRules);
    });

    it('should throw error when API fails', async () => {
      vi.mocked(mockClient.quantsysV2.listWatchRules).mockRejectedValue(new Error('Network error'));

      const tool = createWatchListTool(mockClient);
      await expect(
        tool.execute({}, { signal: new AbortController().signal } as any)
      ).rejects.toThrow('获取盯盘规则列表失败');
    });
  });
});
