import { describe, expect, it } from 'vitest';
import {
  calculateBacktestMetrics,
  calculateDataQualityMetrics,
  calculateJobMetrics,
  calculateSignalMetrics,
  getLatestTrainingRecord,
} from './dashboardMetrics';

describe('dashboardMetrics', () => {
  it('counts buy, sell, and high-confidence signals with ratios', () => {
    const metrics = calculateSignalMetrics([
      { symbol: '000001', signal: 'BUY', confidence: 0.91 },
      { symbol: '000002', signal: 'SELL', confidence: 0.72 },
      { symbol: '000003', signal: 'BUY', confidence: 0.8 },
      { symbol: '000004', signal: 'SELL' },
    ]);

    expect(metrics.total).toBe(4);
    expect(metrics.buyCount).toBe(2);
    expect(metrics.sellCount).toBe(2);
    expect(metrics.highConfidenceCount).toBe(2);
    expect(metrics.buyRatio).toBeCloseTo(0.5);
    expect(metrics.sellRatio).toBeCloseTo(0.5);
  });

  it('averages backtest return, Sharpe, win rate, and worst drawdown', () => {
    const metrics = calculateBacktestMetrics([
      {
        symbol: '000001',
        date: '2026-05-18',
        best_strategy: 's1',
        best_return: 0.12,
        sharpe_ratio: 1.4,
        max_drawdown: -0.08,
        win_rate: 0.6,
      },
      {
        symbol: '000002',
        date: '2026-05-18',
        best_strategy: 's2',
        best_return: -0.02,
        sharpe_ratio: 0.4,
        max_drawdown: -0.18,
        win_rate: 0.45,
      },
    ]);

    expect(metrics.count).toBe(2);
    expect(metrics.averageReturn).toBeCloseTo(0.05);
    expect(metrics.averageSharpe).toBeCloseTo(0.9);
    expect(metrics.averageWinRate).toBeCloseTo(0.525);
    expect(metrics.worstDrawdown).toBe(-0.18);
  });

  it('returns undefined backtest averages and drawdown for empty input', () => {
    const metrics = calculateBacktestMetrics([]);

    expect(metrics.count).toBe(0);
    expect(metrics.averageReturn).toBeUndefined();
    expect(metrics.averageSharpe).toBeUndefined();
    expect(metrics.averageWinRate).toBeUndefined();
    expect(metrics.worstDrawdown).toBeUndefined();
  });

  it('counts active and failed jobs and selects the latest job by updatedAt', () => {
    const jobs = [
      {
        id: 'job-1',
        type: 'signals',
        status: 'success' as const,
        params: {},
        logs: [],
        attempts: 1,
        createdAt: '2026-05-19T08:00:00Z',
        updatedAt: '2026-05-19T08:30:00Z',
      },
      {
        id: 'job-2',
        type: 'backtest',
        status: 'running' as const,
        params: {},
        logs: [],
        attempts: 1,
        createdAt: '2026-05-19T09:00:00Z',
        updatedAt: '2026-05-19T09:20:00Z',
      },
      {
        id: 'job-3',
        type: 'training',
        status: 'queued' as const,
        params: {},
        logs: [],
        attempts: 0,
        createdAt: '2026-05-19T09:10:00Z',
        updatedAt: '2026-05-19T09:10:00Z',
      },
      {
        id: 'job-4',
        type: 'data-update',
        status: 'failed' as const,
        params: {},
        logs: ['failed'],
        attempts: 2,
        createdAt: '2026-05-19T09:30:00Z',
        updatedAt: '2026-05-19T09:40:00Z',
      },
    ];

    const metrics = calculateJobMetrics(jobs);

    expect(metrics.total).toBe(4);
    expect(metrics.activeCount).toBe(2);
    expect(metrics.failedCount).toBe(1);
    expect(metrics.latestJob).toBe(jobs[3]);
  });

  it('calculates data completeness and latest data date', () => {
    const metrics = calculateDataQualityMetrics({
      total_stocks: 3,
      complete_stocks: 2,
      incomplete_stocks: 1,
      stocks: [
        { symbol: '000001', name: 'A', market: 'CN', latest_date: '2026-05-17', data_complete: true },
        { symbol: '000002', name: 'B', market: 'CN', latest_date: '2026-05-19', data_complete: true },
        { symbol: '000003', name: 'C', market: 'CN', latest_date: '2026-05-18', data_complete: false },
      ],
    });

    expect(metrics.totalStocks).toBe(3);
    expect(metrics.completeStocks).toBe(2);
    expect(metrics.incompleteStocks).toBe(1);
    expect(metrics.completenessRate).toBeCloseTo(2 / 3);
    expect(metrics.latestDataDate).toBe('2026-05-19');
  });

  it('returns undefined completeness and date when data status is missing or zero', () => {
    expect(calculateDataQualityMetrics()).toEqual({
      totalStocks: 0,
      completeStocks: 0,
      incompleteStocks: 0,
      completenessRate: undefined,
      latestDataDate: undefined,
    });

    expect(
      calculateDataQualityMetrics({
        total_stocks: 0,
        complete_stocks: 0,
        incomplete_stocks: 0,
        stocks: [],
      }),
    ).toMatchObject({
      completenessRate: undefined,
      latestDataDate: undefined,
    });
  });

  it('selects the newest training record by timestamp', () => {
    const older = {
      timestamp: '2026-05-18T10:00:00Z',
      model_type: 'random_forest',
      n_features: 30,
      total_samples: 1000,
      cv_accuracy: 0.7,
      cv_auc: 0.76,
      test_accuracy: 0.68,
      test_auc: 0.74,
      class_balance: 0.51,
    };
    const newer = {
      timestamp: '2026-05-19T10:00:00Z',
      model_type: 'xgboost',
      n_features: 32,
      total_samples: 1200,
      cv_accuracy: 0.74,
      cv_auc: 0.81,
      test_accuracy: 0.72,
      test_auc: 0.79,
      class_balance: 0.5,
    };

    expect(getLatestTrainingRecord([older, newer])).toBe(newer);
    expect(getLatestTrainingRecord([])).toBeUndefined();
  });
});
