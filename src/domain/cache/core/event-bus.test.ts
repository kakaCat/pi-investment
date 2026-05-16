import { describe, it, expect, beforeEach } from '@jest/globals';
import { EventBus } from './event-bus.js';
import type { CacheEvent } from './types.js';

describe('EventBus', () => {
  let eventBus: EventBus;

  beforeEach(() => {
    eventBus = EventBus.getInstance();
    eventBus.clear();
  });

  it('should be a singleton', () => {
    const instance1 = EventBus.getInstance();
    const instance2 = EventBus.getInstance();
    expect(instance1).toBe(instance2);
  });

  it('should subscribe and emit events', async () => {
    const events: CacheEvent[] = [];
    const handler = async (event: CacheEvent) => {
      events.push(event);
    };

    eventBus.on('cache:invalidate', handler);

    await eventBus.emit({
      type: 'cache:invalidate',
      timestamp: Date.now(),
      payload: { namespace: 'intraday', pattern: 'test:*' }
    });

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('cache:invalidate');
    expect(events[0].payload?.namespace).toBe('intraday');
  });

  it('should support multiple subscribers', async () => {
    let count1 = 0;
    let count2 = 0;

    eventBus.on('cache:invalidate', async () => { count1++; });
    eventBus.on('cache:invalidate', async () => { count2++; });

    await eventBus.emit({
      type: 'cache:invalidate',
      timestamp: Date.now()
    });

    expect(count1).toBe(1);
    expect(count2).toBe(1);
  });

  it('should unsubscribe handlers', async () => {
    let count = 0;
    const handler = async () => { count++; };

    eventBus.on('cache:invalidate', handler);
    await eventBus.emit({ type: 'cache:invalidate', timestamp: Date.now() });
    expect(count).toBe(1);

    eventBus.off('cache:invalidate', handler);
    await eventBus.emit({ type: 'cache:invalidate', timestamp: Date.now() });
    expect(count).toBe(1); // Still 1, not incremented
  });

  it('should handle errors in handlers gracefully', async () => {
    let successCount = 0;

    eventBus.on('cache:invalidate', async () => {
      throw new Error('Handler error');
    });

    eventBus.on('cache:invalidate', async () => {
      successCount++;
    });

    await eventBus.emit({ type: 'cache:invalidate', timestamp: Date.now() });

    // Second handler should still execute despite first handler error
    expect(successCount).toBe(1);
  });

  it('should support wildcard subscriptions', async () => {
    const events: CacheEvent[] = [];

    eventBus.on('cache:*', async (event) => {
      events.push(event);
    });

    await eventBus.emit({ type: 'cache:invalidate', timestamp: Date.now() });
    await eventBus.emit({ type: 'cache:clear', timestamp: Date.now() });
    await eventBus.emit({ type: 'cache:refresh', timestamp: Date.now() });

    expect(events).toHaveLength(3);
  });

  it('should clear all handlers', async () => {
    let count = 0;

    eventBus.on('cache:invalidate', async () => { count++; });
    eventBus.on('cache:clear', async () => { count++; });

    eventBus.clear();

    await eventBus.emit({ type: 'cache:invalidate', timestamp: Date.now() });
    await eventBus.emit({ type: 'cache:clear', timestamp: Date.now() });

    expect(count).toBe(0);
  });

  it('should emit events asynchronously', async () => {
    const order: number[] = [];

    eventBus.on('cache:invalidate', async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
      order.push(2);
    });

    order.push(1);
    await eventBus.emit({ type: 'cache:invalidate', timestamp: Date.now() });
    order.push(3);

    expect(order).toEqual([1, 2, 3]);
  });
});
