/**
 * Model Evaluate Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { getResponseText } from '../test-utils.js';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

const { modelEvaluateTool } = await import('./evaluate-tool.js');

describe('model_evaluate tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(modelEvaluateTool.name).toBe('model_evaluate');
      expect(modelEvaluateTool.label).toBe('模型评估');
    });

    it('should have description', () => {
      expect(modelEvaluateTool.description).toBeDefined();
      expect(modelEvaluateTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(modelEvaluateTool.execute).toBeDefined();
      expect(typeof modelEvaluateTool.execute).toBe('function');
    });
  });

  describe('Evaluate latest model', () => {
    it('should evaluate latest model with default parameter', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        model_type: "xgboost",
        timestamp: "2026-05-25T10:30:00",
        data: {
          n_samples: 5000,
          n_features: 62,
          positive_ratio: 0.35
        },
        cv_results: {
          mean_accuracy: 0.78,
          mean_f1: 0.72,
          fold_scores: [0.76, 0.79, 0.77, 0.80, 0.78]
        },
        test_metrics: {
          accuracy: 0.79,
          precision: 0.75,
          recall: 0.73,
          f1: 0.74,
          auc: 0.82
        },
        feature_importance: [0.15, 0.12, 0.10, 0.08, 0.07],
        feature_names: ["rsi", "macd", "volume_ratio", "pe", "roe"]
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('evaluate_model', { model_id: 'latest' });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBe('latest');
      expect(response.model_type).toBe('xgboost');
    });

    it('should evaluate latest model with explicit parameter', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        model_type: "xgboost",
        timestamp: "2026-05-25T10:30:00"
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', { model_id: 'latest' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('evaluate_model', { model_id: 'latest' });
    });
  });

  describe('Evaluate specific model', () => {
    it('should evaluate model by specific ID', async () => {
      const mockReport = JSON.stringify({
        model_id: "20260525_103000",
        model_type: "xgboost",
        timestamp: "2026-05-25T10:30:00"
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', { model_id: '20260525_103000' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('evaluate_model', { model_id: '20260525_103000' });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBe('20260525_103000');
    });
  });

  describe('Training data statistics validation', () => {
    it('should return training data statistics', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        data: {
          n_samples: 5000,
          n_features: 62,
          positive_ratio: 0.35,
          negative_ratio: 0.65
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect((response as any).data).toBeDefined();
      expect((response as any).data.n_samples).toBe(5000);
      expect((response as any).data.n_features).toBe(62);
      expect((response as any).data.positive_ratio).toBe(0.35);
    });
  });

  describe('Cross-validation results validation', () => {
    it('should return cross-validation results', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        cv_results: {
          mean_accuracy: 0.78,
          std_accuracy: 0.02,
          mean_f1: 0.72,
          std_f1: 0.03,
          fold_scores: [0.76, 0.79, 0.77, 0.80, 0.78]
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.cv_results).toBeDefined();
      expect(response.cv_results.mean_accuracy).toBe(0.78);
      expect(response.cv_results.mean_f1).toBe(0.72);
      expect(response.cv_results.fold_scores).toHaveLength(5);
    });
  });

  describe('Test set metrics validation', () => {
    it('should return test set metrics', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        test_metrics: {
          accuracy: 0.79,
          precision: 0.75,
          recall: 0.73,
          f1: 0.74,
          auc: 0.82
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.test_metrics).toBeDefined();
      expect(response.test_metrics.accuracy).toBe(0.79);
      expect(response.test_metrics.precision).toBe(0.75);
      expect(response.test_metrics.recall).toBe(0.73);
      expect(response.test_metrics.f1).toBe(0.74);
      expect(response.test_metrics.auc).toBe(0.82);
    });
  });

  describe('Feature importance validation', () => {
    it('should return feature importance', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        feature_importance: [0.15, 0.12, 0.10, 0.08, 0.07],
        feature_names: ["rsi", "macd", "volume_ratio", "pe", "roe"]
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.feature_importance).toBeDefined();
      expect(response.feature_importance).toHaveLength(5);
      expect(response.feature_names).toBeDefined();
      expect(response.feature_names).toHaveLength(5);
      expect(response.feature_names[0]).toBe('rsi');
    });
  });

  describe('Confusion matrix validation', () => {
    it('should return confusion matrix', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        test_metrics: {
          confusion_matrix: [[450, 50], [80, 420]]
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.test_metrics.confusion_matrix).toBeDefined();
      expect(response.test_metrics.confusion_matrix).toHaveLength(2);
      expect(response.test_metrics.confusion_matrix[0]).toHaveLength(2);
    });
  });

  describe('Error handling', () => {
    it('should handle model not found error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Model report not found: /path/to/training_report_invalid.json'));

      const result = await (modelEvaluateTool.execute as any)('test-call-id', { model_id: 'invalid' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('evaluate_model', { model_id: 'invalid' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('Model report not found');
    });

    it('should handle daemon connection failure', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('QuantSys daemon is not running'));

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
      expect(response.error).toContain('daemon');
    });
  });

  describe('Response format validation', () => {
    it('should return valid JSON response', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        model_type: "xgboost"
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const responseText = getResponseText(result);
      expect(() => JSON.parse(responseText)).not.toThrow();
    });

    it('should have required fields in response', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        model_type: "xgboost",
        timestamp: "2026-05-25T10:30:00"
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBeDefined();
      expect(response.model_type).toBeDefined();
      expect(response.timestamp).toBeDefined();
    });
  });

  describe('Metrics range validation', () => {
    it('should have metrics in valid range (0-1)', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        test_metrics: {
          accuracy: 0.79,
          precision: 0.75,
          recall: 0.73,
          f1: 0.74,
          auc: 0.82
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      const metrics = response.test_metrics;

      expect(metrics.accuracy).toBeGreaterThanOrEqual(0);
      expect(metrics.accuracy).toBeLessThanOrEqual(1);
      expect(metrics.precision).toBeGreaterThanOrEqual(0);
      expect(metrics.precision).toBeLessThanOrEqual(1);
      expect(metrics.recall).toBeGreaterThanOrEqual(0);
      expect(metrics.recall).toBeLessThanOrEqual(1);
      expect(metrics.f1).toBeGreaterThanOrEqual(0);
      expect(metrics.f1).toBeLessThanOrEqual(1);
      expect(metrics.auc).toBeGreaterThanOrEqual(0);
      expect(metrics.auc).toBeLessThanOrEqual(1);
    });
  });

  describe('Feature count validation', () => {
    it('should have matching feature importance and names count', async () => {
      const mockReport = JSON.stringify({
        model_id: "latest",
        n_features: 62,
        feature_importance: new Array(62).fill(0.01),
        feature_names: new Array(62).fill('feature')
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockReport);

      const result = await (modelEvaluateTool.execute as any)('test-call-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.feature_importance.length).toBe(response.feature_names.length);
      expect(response.feature_importance.length).toBe(62);
    });
  });
});
