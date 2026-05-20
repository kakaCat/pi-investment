import { describe, expect, it } from 'vitest';
import { buildPipelineParams, buildPipelineRunsUrl, derivePipelineProgress, parseSymbolInput } from './QuantPipeline';

describe('QuantPipeline helpers', () => {
  it('normalizes single and multiple stock input into de-duplicated symbols', () => {
    expect(parseSymbolInput(' sz000001, 600036\n600036  SH600519 ')).toEqual([
      '000001',
      '600036',
      '600519'
    ]);
  });

  it('builds symbol-scoped task params for the pipeline', () => {
    expect(buildPipelineParams({
      symbols: ['000001', '600036'],
      days: 180,
      model: 'xgboost',
      futureDays: 5,
      threshold: 0.05
    })).toEqual({
      data_update: { symbols: ['000001', '600036'], days: 180, force: true },
      factor_compute: { symbols: ['000001', '600036'] },
      model_train: {
        symbols: ['000001', '600036'],
        days: 180,
        model: 'xgboost',
        futureDays: 5,
        threshold: 0.05,
        useFeatureEngineering: true
      },
      signal_generate: { symbols: ['000001', '600036'] },
      risk_check: { symbols: ['000001', '600036'] },
      backtest_run: { symbols: ['000001', '600036'], days: 180 },
      daily_report: {}
    });
  });

  it('builds paginated pipeline run list urls', () => {
    expect(buildPipelineRunsUrl(2, 20)).toBe('/api/pipeline/runs?page=2&pageSize=20');
  });

  it('derives progress from persisted pipeline run steps', () => {
    expect(derivePipelineProgress({
      id: 'pipeline_1',
      status: 'running',
      symbols: ['000001'],
      validSymbols: ['000001'],
      invalidSymbols: [],
      params: {},
      currentStep: 'factor_compute',
      progress: 0,
      steps: [
        { key: 'resolve', name: '标的识别', status: 'success' },
        { key: 'data_update', name: '行情补齐', status: 'success' },
        { key: 'factor_compute', name: '因子计算', status: 'running' },
        { key: 'model_train', name: '模型训练', status: 'queued' }
      ],
      createdAt: '2026-05-20T00:00:00Z',
      updatedAt: '2026-05-20T00:00:01Z'
    })).toBe(50);
  });
});
