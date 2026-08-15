/**
 * Async Log Queue for Agent OS
 *
 * 异步批量上传日志到 Agent OS，不阻塞主线程
 */

import { agentOSMemoryWrite, agentOSDecisionRecord } from './cli.js';

export type LogPriority = 'low' | 'normal' | 'high' | 'critical';

export interface LogEntry {
  type: 'memory' | 'decision';
  priority: LogPriority;
  data: any;
  timestamp: number;
  retries?: number;
}

export interface AsyncLogQueueOptions {
  maxQueueSize?: number;        // 最大队列长度
  batchSize?: number;            // 每批上传数量
  flushIntervalMs?: number;      // 自动刷新间隔
  maxRetries?: number;           // 最大重试次数
  retryDelayMs?: number;         // 重试延迟
  onError?: (error: Error, entry: LogEntry) => void;
  onSuccess?: (count: number) => void;
}

/**
 * 异步日志队列
 */
export class AsyncLogQueue {
  private queue: LogEntry[] = [];
  private isRunning = false;
  private flushTimer?: NodeJS.Timeout;
  private options: Required<AsyncLogQueueOptions>;

  constructor(options: AsyncLogQueueOptions = {}) {
    this.options = {
      maxQueueSize: options.maxQueueSize ?? 1000,
      batchSize: options.batchSize ?? 10,
      flushIntervalMs: options.flushIntervalMs ?? 5000, // 5秒
      maxRetries: options.maxRetries ?? 3,
      retryDelayMs: options.retryDelayMs ?? 1000,
      onError: options.onError ?? ((err) => console.error('[AsyncLogQueue] Error:', err)),
      onSuccess: options.onSuccess ?? ((count) => console.log(`[AsyncLogQueue] Uploaded ${count} logs`)),
    };
  }

  /**
   * 启动队列处理器
   */
  start(): void {
    if (this.isRunning) return;

    this.isRunning = true;
    this.scheduleFlush();
    console.log('[AsyncLogQueue] Started');
  }

  /**
   * 停止队列处理器
   */
  async stop(): Promise<void> {
    this.isRunning = false;

    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = undefined;
    }

    // 最后刷新一次
    await this.flush();
    console.log('[AsyncLogQueue] Stopped');
  }

  /**
   * 添加记忆日志
   */
  pushMemory(namespace: string, content: string, metadata?: any, priority: LogPriority = 'normal'): void {
    this.push({
      type: 'memory',
      priority,
      data: { namespace, content, metadata },
      timestamp: Date.now(),
    });
  }

  /**
   * 添加决策日志
   */
  pushDecision(namespace: string, type: string, reasoning: string, result: string, metadata?: any, priority: LogPriority = 'normal'): void {
    this.push({
      type: 'decision',
      priority,
      data: { namespace, type, reasoning, result, metadata },
      timestamp: Date.now(),
    });
  }

  /**
   * 添加日志到队列
   */
  private push(entry: LogEntry): void {
    // 背压控制：队列满时根据优先级决定是否丢弃
    if (this.queue.length >= this.options.maxQueueSize) {
      // 如果是 critical，移除最低优先级的日志
      if (entry.priority === 'critical') {
        const lowPriorityIndex = this.queue.findIndex(e => e.priority === 'low');
        if (lowPriorityIndex >= 0) {
          this.queue.splice(lowPriorityIndex, 1);
          console.warn('[AsyncLogQueue] Queue full, dropped low priority log');
        } else {
          console.warn('[AsyncLogQueue] Queue full, dropping critical log!');
          return;
        }
      } else {
        console.warn(`[AsyncLogQueue] Queue full, dropping ${entry.priority} priority log`);
        return;
      }
    }

    this.queue.push(entry);

    // 如果是 critical，立即刷新
    if (entry.priority === 'critical') {
      this.flush().catch(err => this.options.onError(err, entry));
    }
  }

  /**
   * 调度下次刷新
   */
  private scheduleFlush(): void {
    if (!this.isRunning) return;

    this.flushTimer = setTimeout(() => {
      this.flush()
        .catch(err => console.error('[AsyncLogQueue] Flush error:', err))
        .finally(() => this.scheduleFlush());
    }, this.options.flushIntervalMs);
  }

  /**
   * 立即刷新队列（批量上传）
   */
  async flush(): Promise<void> {
    if (this.queue.length === 0) return;

    // 按优先级排序（高优先级先上传）
    this.queue.sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });

    // 取出一批
    const batch = this.queue.splice(0, this.options.batchSize);

    // 批量上传
    const results = await Promise.allSettled(
      batch.map(entry => this.uploadEntry(entry))
    );

    // 统计结果
    let successCount = 0;
    let failedEntries: LogEntry[] = [];

    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        successCount++;
      } else {
        const entry = batch[index];
        entry.retries = (entry.retries || 0) + 1;

        // 重试次数未超限，重新加入队列
        if (entry.retries < this.options.maxRetries) {
          failedEntries.push(entry);
        } else {
          this.options.onError(result.reason, entry);
        }
      }
    });

    // 将失败的条目重新加入队列
    if (failedEntries.length > 0) {
      this.queue.unshift(...failedEntries);
      console.warn(`[AsyncLogQueue] ${failedEntries.length} entries failed, will retry`);
    }

    if (successCount > 0) {
      this.options.onSuccess(successCount);
    }
  }

  /**
   * 上传单条日志
   */
  private async uploadEntry(entry: LogEntry): Promise<void> {
    if (entry.type === 'memory') {
      const { namespace, content, metadata } = entry.data;
      const result = await agentOSMemoryWrite({
        namespace,
        content,
        metadata,
      });

      if (!result.success) {
        throw new Error(result.error || 'Memory write failed');
      }
    } else if (entry.type === 'decision') {
      const { namespace, type, reasoning, result, metadata } = entry.data;
      const uploadResult = await agentOSDecisionRecord({
        namespace,
        type,
        reasoning,
        result,
        metadata,
      });

      if (!uploadResult.success) {
        throw new Error(uploadResult.error || 'Decision record failed');
      }
    }
  }

  /**
   * 获取队列状态
   */
  getStatus(): {
    queueSize: number;
    isRunning: boolean;
    priorityCounts: Record<LogPriority, number>;
  } {
    const priorityCounts: Record<LogPriority, number> = {
      low: 0,
      normal: 0,
      high: 0,
      critical: 0,
    };

    this.queue.forEach(entry => {
      priorityCounts[entry.priority]++;
    });

    return {
      queueSize: this.queue.length,
      isRunning: this.isRunning,
      priorityCounts,
    };
  }
}

/**
 * 全局单例
 */
let globalQueue: AsyncLogQueue | null = null;

export function initAsyncLogQueue(options?: AsyncLogQueueOptions): AsyncLogQueue {
  if (globalQueue) {
    console.warn('[AsyncLogQueue] Already initialized, returning existing instance');
    return globalQueue;
  }

  globalQueue = new AsyncLogQueue(options);
  globalQueue.start();

  // 进程退出时自动刷新
  process.on('beforeExit', async () => {
    if (globalQueue) {
      await globalQueue.stop();
    }
  });

  return globalQueue;
}

export function getAsyncLogQueue(): AsyncLogQueue {
  if (!globalQueue) {
    throw new Error('[AsyncLogQueue] Not initialized, call initAsyncLogQueue() first');
  }
  return globalQueue;
}
