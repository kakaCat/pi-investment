/**
 * candidates.ts - RFC 008 candidate 登记共享模块（2026-09-03 抽取）
 *
 * 背景：BaseTool 重构(6ec5cd74) 时 PromptEvolverTool 丢失了 candidate 登记调用，
 * 导致 genome_update(stage='candidate') 只写 genome.json history、从不写 candidates.json，
 * ValidationGateTool 读 candidates.json 永远无输入 → 验证门空转（"候选 0"实证坐实）。
 *
 * 本模块统一 candidates.json 的读/写/登记，供 PromptEvolverTool（登记方）与
 * ValidationGateTool（裁决方）共用同一份实现，避免再次出现"两层各写各的"漂移。
 *
 * 观察期候选记录（RFC 008 §3.3）——字段与 ValidationGateTool 读取侧严格对齐
 */
// 2026-09-03 修复：必须顶层 ESM import——tsx 加载时模块作用域无裸 require（ESM），
// 函数内 require('fs') 仅在 CJS/vitest polyfill 下可用，会导致运行时 TypeError 假绿。
import { existsSync, readFileSync, writeFileSync, renameSync } from 'node:fs';

export interface CandidateRecord {
  id: string;
  section: string;
  section_version: number;
  genome_version: string;
  baseline_version: string;
  created_at: string;
  observe_until: string;
  status: 'watching' | 'promoted' | 'rejected';
  note?: string;
  // 2026-08-25 扩展：支持回测腿 + P4 元学习数据地基
  mutation_type?: 'prompt' | 'rule' | 'strategy_param';  // 变异类型（P4 归因用）
  strategy_id?: number;       // 策略参数类 candidate 关联的策略 ID
  params_override?: any;      // 参数变体（未来用）
  backtest_verdict?: {        // 回测腿裁决结果（P4 元学习用）
    passed: boolean;
    windows: Array<{
      label: string;
      symbol: string;
      start_date: string;
      end_date: string;
      sharpe: number;
      return_pct: number;
      max_drawdown_pct: number;
    }>;
    reason: string;
  };
}

/** candidates.json 路径（genomeDir 由调用方经 ctx.genome.genomeDir 获取） */
export function candidatesFilePath(genomeDir: string): string {
  return `${genomeDir}/candidates.json`;
}

export function readCandidates(genomeDir: string): CandidateRecord[] {
  try {
    const p = candidatesFilePath(genomeDir);
    if (!existsSync(p)) return [];
    return JSON.parse(readFileSync(p, 'utf-8'));
  } catch {
    return [];
  }
}

export function writeCandidates(genomeDir: string, list: CandidateRecord[]): void {
  const p = candidatesFilePath(genomeDir);
  const tmp = p + '.tmp';
  writeFileSync(tmp, JSON.stringify(list, null, 2));
  renameSync(tmp, p);
}

/**
 * 登记一条新的 candidate（status='watching'），进入观察期
 * observe_until = now + observeDays 自然日（与 ValidationGateTool 过期判断一致）
 */
export function registerCandidate(opts: {
  genomeDir: string;
  section: string;
  sectionVersion: number;
  genomeVersion: string;
  baselineVersion: string;
  observeDays?: number;
  mutationType?: 'prompt' | 'rule' | 'strategy_param';
  strategyId?: number;
  paramsOverride?: any;
}): CandidateRecord {
  const days = opts.observeDays ?? 5;
  const now = new Date();
  const rec: CandidateRecord = {
    // id 带随机后缀：3 路并发注册同毫秒 Date.now() 会撞车，加后缀保证唯一
    id: `cand_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    section: opts.section,
    section_version: opts.sectionVersion,
    genome_version: opts.genomeVersion,
    baseline_version: opts.baselineVersion,
    created_at: now.toISOString(),
    observe_until: new Date(now.getTime() + days * 86400000).toISOString(),
    status: 'watching',
    mutation_type: opts.mutationType ?? 'prompt',
    strategy_id: opts.strategyId,
    params_override: opts.paramsOverride,
  };
  const list = readCandidates(opts.genomeDir);
  list.push(rec);
  writeCandidates(opts.genomeDir, list);
  return rec;
}
