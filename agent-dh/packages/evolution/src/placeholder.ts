/**
 * Agent OS 占位 fitness 检测（RFC 012 P0：占位退役）
 *
 * 背景（实测坐实，2026-09-03）：
 * Agent OS legacy 进化实现（agent-os/internal/api/evolution_handler.go:182-186）
 * 在 baseline==0（策略从未跑过真实回测 → /api/performance/strategy/{id} 返回空 stats）
 * 时，用 estimated = 0.05 × i（i=1..generations）冒充适应度，且 rationale 自曝
 * "调整风险乘数至 X.XX，在基线收益 0.00% 基础上评估"、"backtest ... to confirm"。
 *
 * 占位特征（双信号，任一命中即判定）：
 *   1. fitness 数值呈 0.05×i 阶梯（浮点容差 1e-9，上限 0.05×10=0.5 与 generations≤10 对应）
 *   2. rationale/action 文本含占位自曝词（"风险乘数" / "基线收益 0.00" / "to confirm"）
 *
 * P0 语义：检测到占位即降级（degraded），绝不向 agent 展示占位数字冒充的
 * "适应度/排名"——空榜+原因 优于 假数据（RFC 012 §0 修复目标）。
 */

export const AGENT_OS_PLACEHOLDER_STEP = 0.05;
/** generations 上限 10 → 占位阶梯上限 0.5 */
export const AGENT_OS_PLACEHOLDER_MAX = 0.5;
const EPS = 1e-9;

/** 是否为 Agent OS 启发式占位分（0.05×i，i≥1） */
export function isAgentOsPlaceholderFitness(value: unknown): boolean {
  if (typeof value !== 'number' || !Number.isFinite(value)) return false;
  if (value <= 0 || value > AGENT_OS_PLACEHOLDER_MAX) return false;
  const k = value / AGENT_OS_PLACEHOLDER_STEP;
  return Math.abs(k - Math.round(k)) < EPS;
}

/** 一组 fitness 是否全部为占位分（空数组不算占位） */
export function allFitnessArePlaceholder(fitnesses: unknown[]): boolean {
  const nums = fitnesses.filter(
    (f): f is number => typeof f === 'number' && Number.isFinite(f)
  );
  return nums.length > 0 && nums.every(isAgentOsPlaceholderFitness);
}

/** 文本是否自曝占位（rationale/action 信号） */
export function textSignalsPlaceholder(...texts: Array<unknown>): boolean {
  return texts.some((t) => {
    if (typeof t !== 'string') return false;
    return (
      t.includes('风险乘数') ||
      t.includes('基线收益 0.00') ||
      t.includes('backtest') && t.includes('to confirm')
    );
  });
}
