/**
 * watch_list 条件渲染语义回归锁（2026-09-11，w-f436d4ea）
 *
 * 背景：后端 quant.watch_rules.conditions 是**列表**，而 engine.py 对列表
 * **逐条独立评估**（每条各有闩锁/冷却/通知）→ 顶层语义是 **OR（任一触发）**；
 * AND 只能通过**单个 combined 节点**表达。
 *
 * 但 WatchListTool 旧实现用 `.join(' AND ')` 渲染，与执行语义相反。实测后果：
 *   1) 10 条合法的「区间突破」规则（跌破 9.85 或 突破 10.2）被渲染成
 *      `price < 9.85 AND price > 10.2`，看起来逻辑恒假、像僵尸规则 ——
 *      2026-09-11 据此后**几乎误删这 10 条规则**（触发 22/24/38 次其实是
 *      闩锁+重新武装的正常结果，不是缺陷）；
 *   2) 更危险的反向误读：把「任一触发」当成「双重确认」，以为自己有确认保护。
 *
 * 本测试锁住：顶层多条件渲染为「或」、单条件不带连接词、combined 节点内保留 AND。
 */

import { describe, it, expect } from 'vitest';
import { WatchListTool } from '../packages/intelligence/src/tools/WatchListTool/WatchListTool.js';

// 渲染发生在 execute() 内（不是 wrap——wrap 只负责把结果包成 ToolResponse），
// 故这里注入桩 client：listWatchRules 返回待渲染规则，listWatchTriggers 返回空
// （→ counts 为空 Map，不影响渲染分支）。
const render = async (rules: any[]) => {
  const tool = new WatchListTool({
    listWatchRules: async () => rules,
    listWatchTriggers: async () => [],
  } as any);
  return await (tool as any).execute({}, {} as any);
};

describe('watch_list 条件渲染语义', () => {
  it('顶层多条件渲染为「或」（引擎逐条独立评估，任一触发）', async () => {
    const out = await render([{
      id: 129, symbol: '601600.SH', enabled: true,
      conditions: [
        { type: 'price_break', params: { price: 9.85, direction: 'below' } },
        { type: 'price_break', params: { price: 10.2, direction: 'above' } },
      ],
    }]);
    expect(out[0].condition).toBe('price < 9.85 或 price > 10.2');
    expect(out[0].condition).not.toContain('AND');
  });

  it('回归：区间突破规则不得再被渲染成自相矛盾的 AND（曾据此险些误删 10 条规则）', async () => {
    const out = await render([{
      id: 120, symbol: '300750.SZ', enabled: true,
      conditions: [
        { type: 'price_break', params: { price: 333, direction: 'below' } },
        { type: 'price_break', params: { price: 340, direction: 'above' } },
      ],
    }]);
    expect(out[0].condition).not.toBe('price < 333 AND price > 340');
    expect(out[0].condition).toBe('price < 333 或 price > 340');
  });

  it('单条件不带任何连接词', async () => {
    const out = await render([{
      id: 101, symbol: '600887',
      conditions: [{ type: 'pnl_pct', params: { pct: -8, direction: 'below' } }],
    }]);
    expect(out[0].condition).toBe('pnl_pct < -8');
    expect(out[0].condition).not.toContain('或');
  });

  it('combined 节点内保留 AND 语义（这才是真正的双重确认）', async () => {
    const out = await render([{
      id: 95, symbol: '600887',
      conditions: [{
        type: 'combined',
        params: {
          operator: 'AND',
          conditions: [
            { type: 'price_break', params: { price: 27, direction: 'above' } },
            { type: 'volume_surge', params: { multiple: 1.3 } },
          ],
        },
      }],
    }]);
    expect(out[0].condition).toBe('(price > 27 且 volume_surge>1.3)');
  });

  it('combined 的 OR 渲染为「或」', async () => {
    const out = await render([{
      id: 1, symbol: '600519',
      conditions: [{
        type: 'combined',
        params: {
          operator: 'OR',
          conditions: [
            { type: 'price_break', params: { price: 2000, direction: 'above' } },
            { type: 'price_break', params: { price: 1800, direction: 'below' } },
          ],
        },
      }],
    }]);
    expect(out[0].condition).toBe('(price > 2000 或 price < 1800)');
  });

  it('空条件仍显式标注（不得静默显示为正常条件）', async () => {
    const out = await render([{ id: 77, symbol: '600000', conditions: [] }]);
    expect(out[0].condition_missing).toBe(true);
    expect(out[0].condition).toContain('未配置触发条件');
  });
});