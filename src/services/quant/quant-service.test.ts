import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { QuantService } from './quant-service';
import fs from 'fs/promises';
import path from 'path';

describe('QuantService', () => {
  const testDir = '.pi-invest-test/quant/strategies';
  let service: QuantService;

  beforeEach(async () => {
    service = new QuantService(testDir);
    await fs.mkdir(testDir, { recursive: true });
  });

  afterEach(async () => {
    await fs.rm('.pi-invest-test', { recursive: true, force: true });
  });

  it('should create a new strategy', async () => {
    const strategy = await service.createStrategy({
      name: 'RSI超卖策略',
      description: '当RSI<30时买入',
      enabled: true,
      screening: {
        market: 'A',
        filters: { pe_range: [0, 30] }
      },
      entry: {
        conditions: [{ indicator: 'rsi', params: {}, operator: '<', value: 30 }],
        logic: 'AND'
      },
      exit: {
        stop_loss: 0.05,
        take_profit: 0.15,
        conditions: []
      },
      position: {
        max_position_pct: 0.1,
        max_stocks: 10
      }
    });

    expect(strategy.id).toMatch(/^strategy_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(strategy.name).toBe('RSI超卖策略');
    expect(strategy.created_at).toBeDefined();
  });

  it('should list all strategies sorted by created_at desc', async () => {
    const strategy1 = await service.createStrategy({
      name: '策略1',
      description: '测试策略1',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: {},
      position: { max_position_pct: 0.1, max_stocks: 10 }
    });

    await new Promise(resolve => setTimeout(resolve, 10));

    const strategy2 = await service.createStrategy({
      name: '策略2',
      description: '测试策略2',
      enabled: false,
      screening: { market: 'HK', filters: {} },
      entry: { conditions: [], logic: 'OR' },
      exit: {},
      position: { max_position_pct: 0.2, max_stocks: 5 }
    });

    const strategies = await service.listStrategies();

    expect(strategies).toHaveLength(2);
    expect(strategies[0].id).toBe(strategy2.id);
    expect(strategies[1].id).toBe(strategy1.id);
  });

  it('should return empty array when no strategies exist', async () => {
    const strategies = await service.listStrategies();
    expect(strategies).toEqual([]);
  });

  it('should get a strategy by id', async () => {
    const created = await service.createStrategy({
      name: 'MACD策略',
      description: 'MACD金叉买入',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: {},
      position: { max_position_pct: 0.15, max_stocks: 8 }
    });

    const retrieved = await service.getStrategy(created.id);

    expect(retrieved).not.toBeNull();
    expect(retrieved?.id).toBe(created.id);
    expect(retrieved?.name).toBe('MACD策略');
  });

  it('should return null when strategy does not exist', async () => {
    const strategy = await service.getStrategy('nonexistent_id');
    expect(strategy).toBeNull();
  });

  it('should update a strategy', async () => {
    const created = await service.createStrategy({
      name: '原始策略',
      description: '原始描述',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: {},
      position: { max_position_pct: 0.1, max_stocks: 10 }
    });

    const updated = await service.updateStrategy(created.id, {
      name: '更新后的策略',
      description: '更新后的描述',
      enabled: false
    });

    expect(updated).not.toBeNull();
    expect(updated?.id).toBe(created.id);
    expect(updated?.name).toBe('更新后的策略');
    expect(updated?.description).toBe('更新后的描述');
    expect(updated?.enabled).toBe(false);
    expect(updated?.created_at).toBe(created.created_at);
  });

  it('should return null when updating non-existent strategy', async () => {
    const result = await service.updateStrategy('nonexistent_id', { name: '新名称' });
    expect(result).toBeNull();
  });

  it('should delete a strategy', async () => {
    const created = await service.createStrategy({
      name: '待删除策略',
      description: '将被删除',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: {},
      position: { max_position_pct: 0.1, max_stocks: 10 }
    });

    const deleted = await service.deleteStrategy(created.id);
    expect(deleted).toBe(true);

    const retrieved = await service.getStrategy(created.id);
    expect(retrieved).toBeNull();
  });

  it('should return false when deleting non-existent strategy', async () => {
    const result = await service.deleteStrategy('nonexistent_id');
    expect(result).toBe(false);
  });

  it('should enable a strategy', async () => {
    const created = await service.createStrategy({
      name: '禁用策略',
      description: '初始禁用',
      enabled: false,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: {},
      position: { max_position_pct: 0.1, max_stocks: 10 }
    });

    const enabled = await service.enableStrategy(created.id);

    expect(enabled).not.toBeNull();
    expect(enabled?.enabled).toBe(true);
  });

  it('should disable a strategy', async () => {
    const created = await service.createStrategy({
      name: '启用策略',
      description: '初始启用',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: {},
      position: { max_position_pct: 0.1, max_stocks: 10 }
    });

    const disabled = await service.disableStrategy(created.id);

    expect(disabled).not.toBeNull();
    expect(disabled?.enabled).toBe(false);
  });

  it('should return null when enabling non-existent strategy', async () => {
    const result = await service.enableStrategy('nonexistent_id');
    expect(result).toBeNull();
  });

  it('should return null when disabling non-existent strategy', async () => {
    const result = await service.disableStrategy('nonexistent_id');
    expect(result).toBeNull();
  });
});
