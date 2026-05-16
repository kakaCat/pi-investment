import type { CacheEvent, CacheEventType } from './types.js';

type EventHandler = (event: CacheEvent) => Promise<void>;

export class EventBus {
  private static instance: EventBus | null = null;
  private handlers: Map<string, Set<EventHandler>>;

  private constructor() {
    this.handlers = new Map();
  }

  static getInstance(): EventBus {
    if (!EventBus.instance) {
      EventBus.instance = new EventBus();
    }
    return EventBus.instance;
  }

  on(eventType: CacheEventType | 'cache:*', handler: EventHandler): void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);
  }

  off(eventType: CacheEventType | 'cache:*', handler: EventHandler): void {
    const handlers = this.handlers.get(eventType);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.handlers.delete(eventType);
      }
    }
  }

  async emit(event: CacheEvent): Promise<void> {
    const promises: Promise<void>[] = [];

    // Emit to specific event type handlers
    const specificHandlers = this.handlers.get(event.type);
    if (specificHandlers) {
      for (const handler of specificHandlers) {
        promises.push(this.safeInvoke(handler, event));
      }
    }

    // Emit to wildcard handlers
    const wildcardHandlers = this.handlers.get('cache:*');
    if (wildcardHandlers) {
      for (const handler of wildcardHandlers) {
        promises.push(this.safeInvoke(handler, event));
      }
    }

    await Promise.all(promises);
  }

  private async safeInvoke(handler: EventHandler, event: CacheEvent): Promise<void> {
    try {
      await handler(event);
    } catch (error) {
      console.error('EventBus handler error:', error);
    }
  }

  clear(): void {
    this.handlers.clear();
  }
}

export const eventBus = EventBus.getInstance();
