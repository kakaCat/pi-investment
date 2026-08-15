/**
 * Agent OS Async Log Queue - 使用示例
 */

import { initAsyncLogQueue, getAsyncLogQueue } from '../infrastructure/agent-os/async-log-queue.js';

// ============================================
// Mock 函数（仅用于示例）
// ============================================

async function performMarketAnalysis() {
  return {
    summary: '市场震荡，建议观望',
    signals: ['买入信号', '持有信号'],
    confidence: 0.75,
    shouldTrade: true,
    action: 'buy',
    symbol: '600519.SH',
  };
}

async function analyzeStockPools() {
  return [
    { id: 'pool-1', name: '高ROE池', summary: '15只股票，平均ROE 18%', topSignals: ['买入信号'], riskLevel: 'low' },
    { id: 'pool-2', name: '低估值池', summary: '20只股票，平均PE 12', topSignals: ['持有'], riskLevel: 'medium' },
  ];
}

// ============================================
// 示例 1: 启动时初始化
// ============================================

// 在 index.ts 中初始化
async function initializeAgentOS() {
  const logQueue = initAsyncLogQueue({
    maxQueueSize: 1000,      // 最大 1000 条日志
    batchSize: 20,           // 每批上传 20 条
    flushIntervalMs: 5000,   // 每 5 秒自动刷新
    maxRetries: 3,           // 失败重试 3 次
    onSuccess: (count) => {
      console.log(`✅ [Agent OS] 成功上传 ${count} 条日志`);
    },
    onError: (error, entry) => {
      console.error(`❌ [Agent OS] 日志上传失败:`, error.message);
      console.error(`   Entry:`, entry.data);
    },
  });

  console.log('✅ Agent OS 异步日志队列已启动');
  return logQueue;
}

// ============================================
// 示例 2: Loop 中使用（非阻塞）
// ============================================

async function executeLoop() {
  const queue = getAsyncLogQueue();

  // Loop 开始
  queue.pushDecision(
    'fin-agent',
    'loop_started',
    'AI 决策循环开始',
    'running',
    { loop_id: 'loop-123', iteration: 1 },
    'normal'
  );

  try {
    // 执行 AI 决策
    const analysis = await performMarketAnalysis();

    // 记录决策过程（异步，不阻塞）
    queue.pushMemory(
      'fin-agent',
      `市场分析完成: ${analysis.summary}`,
      {
        signals: analysis.signals,
        confidence: analysis.confidence,
        timestamp: Date.now(),
      },
      'normal'
    );

    // 记录关键决策（高优先级）
    if (analysis.shouldTrade) {
      queue.pushDecision(
        'fin-agent',
        'trade_signal',
        `生成交易信号: ${analysis.action}`,
        'approved',
        {
          action: analysis.action,
          symbol: analysis.symbol,
          confidence: analysis.confidence,
        },
        'high' // 交易信号是高优先级
      );
    }

    // Loop 完成
    queue.pushDecision(
      'fin-agent',
      'loop_completed',
      'AI 决策循环完成',
      'success',
      { loop_id: 'loop-123', duration_ms: 1234 },
      'normal'
    );
  } catch (error: any) {
    // 错误日志（关键优先级，立即上传）
    queue.pushDecision(
      'fin-agent',
      'loop_failed',
      `Loop 执行失败: ${error.message}`,
      'error',
      {
        loop_id: 'loop-123',
        error: error.stack,
        timestamp: Date.now(),
      },
      'critical' // 错误是关键优先级，立即上传
    );

    throw error;
  }
}

// ============================================
// 示例 3: 定时任务中使用
// ============================================

async function morningAnalysisTask() {
  const queue = getAsyncLogQueue();

  // 任务开始
  queue.pushDecision(
    'fin-agent',
    'task_started',
    '开始执行晨间分析任务',
    'running',
    { task_name: 'morning_analysis' },
    'normal'
  );

  const startTime = Date.now();

  try {
    // 执行分析
    const pools = await analyzeStockPools();

    // 记录每个池子的分析结果
    for (const pool of pools) {
      queue.pushMemory(
        'fin-agent',
        `${pool.name}: ${pool.summary}`,
        {
          pool_id: pool.id,
          top_signals: pool.topSignals,
          risk_level: pool.riskLevel,
        },
        'normal'
      );
    }

    // 任务完成
    queue.pushDecision(
      'fin-agent',
      'task_completed',
      `晨间分析任务完成，分析了 ${pools.length} 个股票池`,
      'success',
      {
        task_name: 'morning_analysis',
        duration_ms: Date.now() - startTime,
        pools_count: pools.length,
      },
      'normal'
    );
  } catch (error: any) {
    // 任务失败
    queue.pushDecision(
      'fin-agent',
      'task_failed',
      `晨间分析任务失败: ${error.message}`,
      'error',
      {
        task_name: 'morning_analysis',
        duration_ms: Date.now() - startTime,
        error: error.stack,
      },
      'high' // 任务失败是高优先级
    );

    throw error;
  }
}

// ============================================
// 示例 4: Memory 蒸馏（批量写入）
// ============================================

async function distillSessionMemories(sessionId: string, memories: any[]) {
  const queue = getAsyncLogQueue();

  queue.pushDecision(
    'memory-agent',
    'distill_started',
    `开始蒸馏会话 ${sessionId} 的记忆`,
    'running',
    { session_id: sessionId, memories_count: memories.length },
    'normal'
  );

  // 批量写入记忆（队列会自动批量上传）
  for (const memory of memories) {
    queue.pushMemory(
      'memory-agent',
      memory.content,
      {
        session_id: sessionId,
        importance: memory.importance,
        category: memory.category,
      },
      memory.importance > 0.8 ? 'high' : 'normal'
    );
  }

  queue.pushDecision(
    'memory-agent',
    'distill_completed',
    `完成蒸馏会话 ${sessionId}`,
    'success',
    {
      session_id: sessionId,
      memories_written: memories.length,
    },
    'normal'
  );
}

// ============================================
// 示例 5: 进程退出时自动刷新
// ============================================

process.on('SIGINT', async () => {
  console.log('\n正在关闭 Agent OS 日志队列...');
  const queue = getAsyncLogQueue();

  // 记录关闭事件
  queue.pushDecision(
    'system',
    'shutdown',
    'Agent 进程正在关闭',
    'shutdown',
    { timestamp: Date.now() },
    'critical' // 关键事件，立即上传
  );

  // 停止队列（自动刷新剩余日志）
  await queue.stop();
  console.log('✅ Agent OS 日志队列已关闭');

  process.exit(0);
});

// ============================================
// 示例 6: 监控队列状态
// ============================================

setInterval(() => {
  const queue = getAsyncLogQueue();
  const status = queue.getStatus();

  console.log('[Agent OS Queue]', {
    size: status.queueSize,
    running: status.isRunning,
    priorities: status.priorityCounts,
  });

  // 队列积压过多时告警
  if (status.queueSize > 800) {
    console.warn(`⚠️  日志队列积压过多: ${status.queueSize}/1000`);
  }
}, 60000); // 每分钟检查一次

// ============================================
// 导出便捷函数
// ============================================

export {
  initializeAgentOS,
  executeLoop,
  morningAnalysisTask,
  distillSessionMemories,
};
