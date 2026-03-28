/**
 * 性能监控模块
 * 实时追踪 Agent 的性能指标
 */

export interface PerformanceMetrics {
  llm: {
    calls: number;
    totalLatency: number;
    avgLatency: number;
    tokens: {
      prompt: number;
      completion: number;
      total: number;
    };
  };
  tools: Map<string, {
    calls: number;
    totalTime: number;
    avgTime: number;
    errors: number;
  }>;
  session: {
    startTime: number;
    turns: number;
    duration: number;
  };
}

interface CallRecord {
  id: string;
  startTime: number;
  type: 'llm' | 'tool';
  name?: string;
}

export class PerformanceMonitor {
  private metrics: PerformanceMetrics;
  private activeCalls: Map<string, CallRecord>;

  constructor() {
    this.metrics = {
      llm: {
        calls: 0,
        totalLatency: 0,
        avgLatency: 0,
        tokens: { prompt: 0, completion: 0, total: 0 },
      },
      tools: new Map(),
      session: {
        startTime: Date.now(),
        turns: 0,
        duration: 0,
      },
    };
    this.activeCalls = new Map();
  }

  /**
   * 开始 LLM 调用追踪
   */
  startLLMCall(): string {
    const id = `llm_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    this.activeCalls.set(id, {
      id,
      startTime: Date.now(),
      type: 'llm',
    });
    return id;
  }

  /**
   * 结束 LLM 调用追踪
   */
  endLLMCall(id: string, tokens: any, latency?: number): void {
    const call = this.activeCalls.get(id);
    if (!call) return;

    const duration = latency ?? Date.now() - call.startTime;

    this.metrics.llm.calls++;
    this.metrics.llm.totalLatency += duration;
    this.metrics.llm.avgLatency = this.metrics.llm.totalLatency / this.metrics.llm.calls;

    if (tokens) {
      this.metrics.llm.tokens.prompt += tokens.input_tokens || 0;
      this.metrics.llm.tokens.completion += tokens.output_tokens || 0;
      this.metrics.llm.tokens.total += (tokens.input_tokens || 0) + (tokens.output_tokens || 0);
    }

    this.activeCalls.delete(id);
  }

  /**
   * 开始工具调用追踪
   */
  startToolCall(toolName: string): string {
    const id = `tool_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    this.activeCalls.set(id, {
      id,
      startTime: Date.now(),
      type: 'tool',
      name: toolName,
    });
    return id;
  }

  /**
   * 结束工具调用追踪
   */
  endToolCall(id: string, toolName: string, success: boolean, duration?: number): void {
    const call = this.activeCalls.get(id);
    if (!call) return;

    const elapsed = duration ?? Date.now() - call.startTime;

    if (!this.metrics.tools.has(toolName)) {
      this.metrics.tools.set(toolName, {
        calls: 0,
        totalTime: 0,
        avgTime: 0,
        errors: 0,
      });
    }

    const toolStats = this.metrics.tools.get(toolName)!;
    toolStats.calls++;
    toolStats.totalTime += elapsed;
    toolStats.avgTime = toolStats.totalTime / toolStats.calls;
    if (!success) {
      toolStats.errors++;
    }

    this.activeCalls.delete(id);
  }

  /**
   * 记录一个对话轮次
   */
  recordTurn(): void {
    this.metrics.session.turns++;
    this.metrics.session.duration = Date.now() - this.metrics.session.startTime;
  }

  /**
   * 获取性能报告（文本格式）
   */
  getReport(): string {
    const lines: string[] = [];
    lines.push('');
    lines.push('═══════════════════════════════════════════════════');
    lines.push('📊 性能报告');
    lines.push('═══════════════════════════════════════════════════');
    lines.push('');

    // 会话统计
    const sessionDurationMin = (this.metrics.session.duration / 1000 / 60).toFixed(2);
    lines.push('🕐 会话统计:');
    lines.push(`  - 总时长: ${sessionDurationMin} 分钟`);
    lines.push(`  - 对话轮次: ${this.metrics.session.turns}`);
    lines.push('');

    // LLM 统计
    lines.push('🤖 LLM 调用:');
    lines.push(`  - 调用次数: ${this.metrics.llm.calls}`);
    lines.push(`  - 平均延迟: ${this.metrics.llm.avgLatency.toFixed(0)} ms`);
    lines.push(`  - Token 使用:`);
    lines.push(`    • 输入: ${this.metrics.llm.tokens.prompt.toLocaleString()}`);
    lines.push(`    • 输出: ${this.metrics.llm.tokens.completion.toLocaleString()}`);
    lines.push(`    • 总计: ${this.metrics.llm.tokens.total.toLocaleString()}`);
    lines.push('');

    // 工具统计
    if (this.metrics.tools.size > 0) {
      lines.push('🔧 工具调用:');
      const sortedTools = Array.from(this.metrics.tools.entries())
        .sort((a, b) => b[1].calls - a[1].calls);

      for (const [name, stats] of sortedTools) {
        const errorRate = stats.calls > 0 ? ((stats.errors / stats.calls) * 100).toFixed(1) : '0.0';
        lines.push(`  - ${name}:`);
        lines.push(`    • 调用: ${stats.calls} 次`);
        lines.push(`    • 平均耗时: ${stats.avgTime.toFixed(0)} ms`);
        lines.push(`    • 错误率: ${errorRate}%`);
      }
      lines.push('');
    }

    lines.push('═══════════════════════════════════════════════════');
    return lines.join('\n');
  }

  /**
   * 导出 JSON 格式
   */
  exportJSON(): string {
    return JSON.stringify({
      ...this.metrics,
      tools: Array.from(this.metrics.tools.entries()).map(([name, stats]) => ({
        name,
        ...stats,
      })),
    }, null, 2);
  }

  /**
   * 重置所有指标
   */
  reset(): void {
    this.metrics = {
      llm: {
        calls: 0,
        totalLatency: 0,
        avgLatency: 0,
        tokens: { prompt: 0, completion: 0, total: 0 },
      },
      tools: new Map(),
      session: {
        startTime: Date.now(),
        turns: 0,
        duration: 0,
      },
    };
    this.activeCalls.clear();
  }

  /**
   * 获取当前指标（只读）
   */
  getMetrics(): Readonly<PerformanceMetrics> {
    return this.metrics;
  }
}
