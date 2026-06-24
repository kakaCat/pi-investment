/**
 * Model Train Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

const { modelTrainTool } = await import('./train-tool.js');

// Helper to extract text from tool result
function getResponseText(result: any): string {
  return ((result.content[0] as any).text);
}

describe('model_train tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(modelTrainTool.name).toBe('model_train');
      expect(modelTrainTool.label).toBe('训练模型');
    });

    it('should have description', () => {
      expect(modelTrainTool.description).toBeDefined();
      expect(modelTrainTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(modelTrainTool.execute).toBeDefined();
      expect(typeof modelTrainTool.execute).toBe('function');
    });
  });

  describe('Default parameters training', () => {
    it('should train with default parameters', async () => {
      const mockTrainingReport = JSON.stringify({
        model_type: 'xgboost',
        timestamp: '2026-05-25T10:00:00',
        data: {
          n_samples: 1000,
          n_features: 62,
          train_size: 800,
          test_size: 200
        },
        cv_results: {
          mean_accuracy: 0.75,
          std_accuracy: 0.05,
          mean_f1: 0.72,
          std_f1: 0.04
        },
        test_metrics: {
          accuracy: 0.76,
          precision: 0.74,
          recall: 0.73,
          f1: 0.735
        },
        feature_importance: [0.15, 0.12, 0.10],
        feature_names: ['rsi', 'macd', 'volume_ratio']
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockTrainingReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 5
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_type).toBe('xgboost');
      expect(response.test_metrics).toBeDefined();
      expect(response.feature_importance).toBeDefined();
    });
  });

  describe('Model type specification', () => {
    it('should train xgboost model when specified', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        model_type: 'xgboost'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 5
      });
    });

    it('should train lightgbm model when specified', async () => {
      const mockReport = JSON.stringify({
        model_type: 'lightgbm',
        test_metrics: { accuracy: 0.77 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        model_type: 'lightgbm'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'lightgbm',
        days: 180,
        future_days: 5,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 5
      });
    });
  });

  describe('Custom training days', () => {
    it('should use custom days parameter', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        data: { n_samples: 500 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        days: 90
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 90,
        future_days: 5,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 5
      });
    });

    it('should use custom days parameter with large value', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        data: { n_samples: 2000 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        days: 365
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 365,
        future_days: 5,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 5
      });
    });
  });

  describe('Custom future days', () => {
    it('should use custom future_days parameter', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        future_days: 10
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 10,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 5
      });
    });
  });

  describe('Custom return threshold', () => {
    it('should use custom return_threshold parameter', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        return_threshold: 0.10
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.10,
        symbols: undefined,
        cv_splits: 5
      });
    });

    it('should accept small return threshold', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        return_threshold: 0.01
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.01,
        symbols: undefined,
        cv_splits: 5
      });
    });
  });

  describe('Custom stock symbols', () => {
    it('should train on specified stock list', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        data: { n_samples: 300 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        symbols: ['600519', '000858', '600036']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.05,
        symbols: ['600519', '000858', '600036'],
        cv_splits: 5
      });
    });

    it('should train on single stock', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        data: { n_samples: 100 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        symbols: ['600519']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.05,
        symbols: ['600519'],
        cv_splits: 5
      });
    });
  });

  describe('Custom cross-validation splits', () => {
    it('should use custom cv_splits parameter', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        cv_results: { mean_accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        cv_splits: 10
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'xgboost',
        days: 180,
        future_days: 5,
        return_threshold: 0.05,
        symbols: undefined,
        cv_splits: 10
      });
    });
  });

  describe('Combined parameters', () => {
    it('should handle multiple custom parameters', async () => {
      const mockReport = JSON.stringify({
        model_type: 'lightgbm',
        data: { n_samples: 500 },
        test_metrics: { accuracy: 0.78 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      await (modelTrainTool.execute as any)('test-call-id', {
        model_type: 'lightgbm',
        days: 120,
        future_days: 7,
        return_threshold: 0.08,
        symbols: ['600519', '000858'],
        cv_splits: 8
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('train_model', {
        model_type: 'lightgbm',
        days: 120,
        future_days: 7,
        return_threshold: 0.08,
        symbols: ['600519', '000858'],
        cv_splits: 8
      });
    });
  });

  describe('Error handling - Invalid parameters', () => {
    it('should reject negative days', async () => {
      const result = await (modelTrainTool.execute as any)('test-call-id', {
        days: -10
      });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('days 参数必须大于 0');
    });

    it('should reject zero days', async () => {
      const result = await (modelTrainTool.execute as any)('test-call-id', {
        days: 0
      });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('days 参数必须大于 0');
    });

    it('should reject negative future_days', async () => {
      const result = await (modelTrainTool.execute as any)('test-call-id', {
        future_days: -5
      });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('future_days 参数必须大于 0');
    });

    it('should reject return_threshold below 0', async () => {
      const result = await (modelTrainTool.execute as any)('test-call-id', {
        return_threshold: -0.05
      });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('return_threshold 参数必须在 0 到 1 之间');
    });

    it('should reject return_threshold above 1', async () => {
      const result = await (modelTrainTool.execute as any)('test-call-id', {
        return_threshold: 1.5
      });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('return_threshold 参数必须在 0 到 1 之间');
    });

    it('should reject cv_splits less than 2', async () => {
      const result = await (modelTrainTool.execute as any)('test-call-id', {
        cv_splits: 1
      });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('cv_splits 参数必须大于等于 2');
    });
  });

  describe('Error handling - Daemon failures', () => {
    it('should handle daemon connection failure', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(
        new Error('QuantSys daemon is not running')
      );

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('QuantSys daemon is not running');
    });

    it('should handle training failure', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(
        new Error('Insufficient training data')
      );

      const result = await (modelTrainTool.execute as any)('test-call-id', {
        symbols: ['INVALID']
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('Insufficient training data');
    });

    it('should handle timeout error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(
        new Error('Request timeout after 150000ms')
      );

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('timeout');
    });
  });

  describe('Response format validation', () => {
    it('should return valid JSON response', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        timestamp: '2026-05-25T10:00:00',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse(getResponseText(result));
      expect(response).toBeDefined();
      expect(typeof response).toBe('object');
    });

    it('should include model_type in response', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.model_type).toBeDefined();
      expect(['xgboost', 'lightgbm']).toContain(response.model_type);
    });
  });

  describe('Training report field validation', () => {
    it('should include data statistics in report', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        data: {
          n_samples: 1000,
          n_features: 62,
          train_size: 800,
          test_size: 200
        },
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect((response as any).data).toBeDefined();
      expect((response as any).data.n_samples).toBeGreaterThan(0);
      expect((response as any).data.n_features).toBeGreaterThan(0);
    });

    it('should include cv_results in report', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        cv_results: {
          mean_accuracy: 0.75,
          std_accuracy: 0.05,
          mean_f1: 0.72,
          std_f1: 0.04
        },
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.cv_results).toBeDefined();
      expect(response.cv_results.mean_accuracy).toBeGreaterThan(0);
      expect(response.cv_results.mean_accuracy).toBeLessThanOrEqual(1);
    });

    it('should include test_metrics in report', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        test_metrics: {
          accuracy: 0.76,
          precision: 0.74,
          recall: 0.73,
          f1: 0.735
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.test_metrics).toBeDefined();
      expect(response.test_metrics.accuracy).toBeDefined();
      expect(response.test_metrics.precision).toBeDefined();
      expect(response.test_metrics.recall).toBeDefined();
      expect(response.test_metrics.f1).toBeDefined();
    });

    it('should include feature_importance in report', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        feature_importance: [0.15, 0.12, 0.10, 0.08],
        feature_names: ['rsi', 'macd', 'volume_ratio', 'kdj'],
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.feature_importance).toBeDefined();
      expect(Array.isArray(response.feature_importance)).toBe(true);
      expect(response.feature_importance.length).toBeGreaterThan(0);
    });

    it('should include feature_names in report', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        feature_importance: [0.15, 0.12, 0.10],
        feature_names: ['rsi', 'macd', 'volume_ratio'],
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.feature_names).toBeDefined();
      expect(Array.isArray(response.feature_names)).toBe(true);
      expect(response.feature_names.length).toBe(response.feature_importance.length);
    });

    it('should include timestamp in report', async () => {
      const mockReport = JSON.stringify({
        model_type: 'xgboost',
        timestamp: '2026-05-25T10:00:00',
        test_metrics: { accuracy: 0.75 }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelTrainTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.timestamp).toBeDefined();
      expect(typeof response.timestamp).toBe('string');
    });
  });
});
