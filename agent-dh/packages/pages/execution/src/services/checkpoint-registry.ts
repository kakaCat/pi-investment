import { Checkpoint } from '../types/index.js';

// Real checkpoint registry based on 2026-09-03 verification
// Maps to actual scheduler tasks and v2 endpoints
export const CHECKPOINTS: Checkpoint[] = [
  // M0 - Data Foundation
  {
    id: 'm0_kline_sync',
    line: 'engine',
    module: 'M0',
    name: '日K同步',
    verify: { type: 'scheduler_task', taskName: '每日数据更新' },
    expectDays: '1-5',
    expectTime: '22:30',
    graceMinutes: 30,
    blocksFlow: ['m1_regime', 'm1_themes', 'm2_pool_refresh', 'm3_signal_gen']
  },
  {
    id: 'm0_data_quality',
    line: 'engine',
    module: 'M0',
    name: '数据质量检查',
    verify: { type: 'scheduler_task', taskName: '每日数据质量检查' },
    expectDays: '0-6',
    expectTime: '22:00',
    graceMinutes: 30,
    blocksFlow: ['m1_regime']
  },
  {
    id: 'm0_fin_weekly',
    line: 'engine',
    module: 'M0',
    name: '周度财务更新',
    verify: { type: 'scheduler_task', taskName: '每周财务数据更新' },
    expectDays: '6',
    expectTime: '18:30',
    graceMinutes: 60,
    blocksFlow: ['m2_pool_refresh']
  },

  // M1 - Market Perception
  {
    id: 'm1_regime',
    line: 'engine',
    module: 'M1',
    name: 'regime落库',
    verify: { type: 'v2_regime' },
    expectDays: '1-5',
    expectTime: '22:10',
    graceMinutes: 30,
    blocksFlow: ['m4_risk_check']
  },
  {
    id: 'm1_themes',
    line: 'engine',
    module: 'M1',
    name: '主线主题落库',
    verify: { type: 'v2_themes' },
    expectDays: '1-5',
    expectTime: '22:10',
    graceMinutes: 30,
    blocksFlow: ['m2_pool_refresh', 'm3_signal_gen']
  },

  // M2 - Stock Pool
  {
    id: 'm2_pool_refresh',
    line: 'engine',
    module: 'M2',
    name: '股票池刷新',
    verify: { type: 'scheduler_task', taskName: 'daily-pool-refresh' },
    expectDays: '0-4',
    expectTime: '23:00',
    graceMinutes: 30,
    blocksFlow: ['m3_signal_gen']
  },

  // M3 - Signal & Execution
  {
    id: 'm3_signal_gen',
    line: 'engine',
    module: 'M3',
    name: '信号生成',
    verify: { type: 'scheduler_task', taskName: '每日信号生成' },
    expectDays: '1-5',
    expectTime: '08:30',
    graceMinutes: 30
  },
  {
    id: 'm3_signal_exec',
    line: 'engine',
    module: 'M3',
    name: '信号执行',
    verify: { type: 'scheduler_task', taskName: '每日信号执行' },
    expectDays: '1-5',
    expectTime: '07:30',
    graceMinutes: 30
  },
  {
    id: 'm3_perf_backfill',
    line: 'engine',
    module: 'M3',
    name: '胜率回填',
    verify: { type: 'scheduler_task', taskName: 'signal-perf-backfill-daily' },
    expectDays: '1-5',
    expectTime: '15:45',
    graceMinutes: 30,
    blocksFlow: ['l1_strategy_validate']
  },

  // M4 - Risk Control
  {
    id: 'm4_risk_check',
    line: 'engine',
    module: 'M4',
    name: '风控/熔断',
    verify: { type: 'scheduler_task', taskName: 'v13-risk-check' },
    expectDays: '1-5',
    expectTime: '08:00',
    graceMinutes: 30,
    blocksFlow: ['m5_trade_verify']
  },

  // M5 - Trade Verification
  {
    id: 'm5_trade_verify',
    line: 'engine',
    module: 'M5',
    name: '交易对账',
    verify: { type: 'scheduler_task', taskName: 'daily_trade_verify' },
    expectDays: '1-5',
    expectTime: '15:35',
    graceMinutes: 30
  },

  // M6 - Experience
  {
    id: 'm6_experience',
    line: 'engine',
    module: 'M6',
    name: '盘后经验沉淀',
    verify: { type: 'v2_memory_kind', kind: 'experience' },
    expectDays: '1-5',
    expectTime: '16:00',
    graceMinutes: 60,
    blocksFlow: ['l1_strategy_validate', 'l2_distill']
  },

  // L1 - Strategy Validation
  {
    id: 'l1_strategy_validate',
    line: 'autonomy',
    module: 'L1',
    name: '策略验证',
    verify: { type: 'scheduler_task', taskName: 'daily-strategy-validation' },
    expectDays: '1-5',
    expectTime: '13:00',
    graceMinutes: 30
  },

  // L2 - Knowledge Distillation
  {
    id: 'l2_distill',
    line: 'autonomy',
    module: 'L2',
    name: '经验蒸馏',
    verify: { type: 'genome_file', file: 'candidates.json' },
    expectDays: '1-5',
    expectTime: '16:00',
    graceMinutes: 60
  },

  // L3 - Validation Gate
  {
    id: 'l3_gate',
    line: 'autonomy',
    module: 'L3',
    name: '验证门裁决',
    verify: { type: 'genome_file', file: 'genome.json' },
    expectDays: '0-6',
    expectTime: '23:30',
    graceMinutes: 60
  },

  // L4 - Weekly Report
  {
    id: 'l4_weekly_report',
    line: 'autonomy',
    module: 'L4',
    name: '周报',
    verify: { type: 'scheduler_task', taskName: 'v13-weekly-report' },
    expectDays: '0',
    expectTime: '01:00',
    graceMinutes: 60
  }
];

export function getCheckpointById(id: string): Checkpoint | undefined {
  return CHECKPOINTS.find(cp => cp.id === id);
}

export function getCheckpointsByModule(module: string): Checkpoint[] {
  return CHECKPOINTS.filter(cp => cp.module === module);
}

export function getCheckpointsByLine(line: 'engine' | 'autonomy'): Checkpoint[] {
  return CHECKPOINTS.filter(cp => cp.line === line);
}
