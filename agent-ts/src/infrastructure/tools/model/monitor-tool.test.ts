/**
 * Model Monitor Tool Tests - Business Logic Coverage
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

const { modelMonitorTool } = await import('./monitor-tool.js');

// Helper to extract text from tool result
function getResponseText(result: any): string {
  return ((result.content[0] as any).text);
}

describe('modelMonitorTool - Tool Definition', () => {
  it('should have correct tool name', () => {
    expect(modelMonitorTool.name).toBe('model_monitor');
  });

  it('should have correct label', () => {
    expect(modelMonitorTool.label).toBe('模型监控');
  });

  it('should have description mentioning drift detection', () => {
    expect(modelMonitorTool.description).toContain('特征漂移');
    expect(modelMonitorTool.description).toContain('重新训练');
  });

  it('should have parameters object', () => {
    expect(modelMonitorTool.parameters).toBeDefined();
    expect(typeof modelMonitorTool.parameters).toBe('object');
  });

  it('should have execute function', () => {
    expect(modelMonitorTool.execute).toBeDefined();
    expect(typeof modelMonitorTool.execute).toBe('function');
  });

  it('should have optional model_id parameter', () => {
    const params = modelMonitorTool.parameters as any;
    expect(params.properties).toBeDefined();
    expect(params.properties.model_id).toBeDefined();
  });
});

describe('modelMonitorTool - Business Logic', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('monitoring latest model', () => {
    it('should monitor latest model with default parameters', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [
          {
            feature: 'rsi_14',
            train_importance: 0.08,
            current_importance: 0.09,
            drift: 0.01
          }
        ],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('monitor_model', {
        model_id: 'latest'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBe('latest');
      expect(response.drift_score).toBeDefined();
      expect(response.drift_threshold).toBeDefined();
      expect(response.is_drifted).toBeDefined();
      expect(response.top_drifts).toBeDefined();
      expect(response.recommendation).toBeDefined();
    });

    it('should monitor latest model explicitly', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'latest'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBe('latest');
    });
  });

  describe('monitoring specific model', () => {
    it('should monitor specified model by ID', async () => {
      const mockResponse = JSON.stringify({
        model_id: '20260525_120000',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: '20260525_120000'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('monitor_model', {
        model_id: '20260525_120000'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBe('20260525_120000');
    });
  });

  describe('drift score validation', () => {
    it('should return valid drift score', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(typeof response.drift_score).toBe('number');
      expect(response.drift_score).toBeGreaterThanOrEqual(0);
    });

    it('should return drift score within reasonable range', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.drift_score).toBeLessThan(1.0);
    });
  });

  describe('drift threshold validation', () => {
    it('should return drift threshold', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(typeof response.drift_threshold).toBe('number');
      expect(response.drift_threshold).toBe(0.1);
    });
  });

  describe('drift flag validation', () => {
    it('should return false when model is stable', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'stable_model',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'stable_model'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.is_drifted).toBe(false);
      expect(response.drift_score).toBeLessThan(response.drift_threshold);
    });

    it('should return true when model has drifted', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'drifted_model',
        drift_score: 0.15,
        drift_threshold: 0.1,
        is_drifted: true,
        top_drifts: [],
        recommendation: 'Retrain model'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'drifted_model'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.is_drifted).toBe(true);
      expect(response.drift_score).toBeGreaterThan(response.drift_threshold);
    });
  });

  describe('top drift features validation', () => {
    it('should return top drift features array', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [
          {
            feature: 'rsi_14',
            train_importance: 0.08,
            current_importance: 0.09,
            drift: 0.01
          }
        ],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(Array.isArray(response.top_drifts)).toBe(true);
      expect(response.top_drifts.length).toBeGreaterThan(0);
    });

    it('should have correct feature drift structure', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [
          {
            feature: 'rsi_14',
            train_importance: 0.08,
            current_importance: 0.09,
            drift: 0.01
          }
        ],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      const firstDrift = response.top_drifts[0];
      expect(firstDrift.feature).toBeDefined();
      expect(typeof firstDrift.feature).toBe('string');
      expect(typeof firstDrift.train_importance).toBe('number');
      expect(typeof firstDrift.current_importance).toBe('number');
      expect(typeof firstDrift.drift).toBe('number');
    });

    it('should sort features by drift magnitude', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'drifted_model',
        drift_score: 0.15,
        drift_threshold: 0.1,
        is_drifted: true,
        top_drifts: [
          {
            feature: 'rsi_14',
            train_importance: 0.08,
            current_importance: 0.15,
            drift: 0.07
          },
          {
            feature: 'macd_signal',
            train_importance: 0.06,
            current_importance: 0.12,
            drift: 0.06
          },
          {
            feature: 'volume_ratio',
            train_importance: 0.05,
            current_importance: 0.09,
            drift: 0.04
          }
        ],
        recommendation: 'Retrain model'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'drifted_model'
      });

      const response = JSON.parse(getResponseText(result));
      const drifts = response.top_drifts.map((d: any) => d.drift);

      // Check descending order
      for (let i = 0; i < drifts.length - 1; i++) {
        expect(drifts[i]).toBeGreaterThanOrEqual(drifts[i + 1]);
      }
    });
  });

  describe('retrain recommendation validation', () => {
    it('should recommend stability when model is stable', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'stable_model',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'stable_model'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.recommendation).toBe('Model is stable');
    });

    it('should recommend retraining when model has drifted', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'drifted_model',
        drift_score: 0.15,
        drift_threshold: 0.1,
        is_drifted: true,
        top_drifts: [],
        recommendation: 'Retrain model'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'drifted_model'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.recommendation).toBe('Retrain model');
    });
  });

  describe('error handling', () => {
    it('should handle model not found error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Model not found: nonexistent'));

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'nonexistent'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('Model not found');
    });

    it('should handle daemon connection failure', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Daemon connection failed'));

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'daemon_error'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('Daemon connection failed');
    });
  });

  describe('response format validation', () => {
    it('should return valid JSON response', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const text = getResponseText(result);
      expect(() => JSON.parse(text)).not.toThrow();
    });

    it('should have all required fields in response', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response).toHaveProperty('model_id');
      expect(response).toHaveProperty('drift_score');
      expect(response).toHaveProperty('drift_threshold');
      expect(response).toHaveProperty('is_drifted');
      expect(response).toHaveProperty('top_drifts');
      expect(response).toHaveProperty('recommendation');
    });
  });

  describe('drift score range validation', () => {
    it('should have non-negative drift score', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'latest',
        drift_score: 0.05,
        drift_threshold: 0.1,
        is_drifted: false,
        top_drifts: [],
        recommendation: 'Model is stable'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {});

      const response = JSON.parse(getResponseText(result));
      expect(response.drift_score).toBeGreaterThanOrEqual(0);
    });

    it('should have reasonable drift score upper bound', async () => {
      const mockResponse = JSON.stringify({
        model_id: 'drifted_model',
        drift_score: 0.15,
        drift_threshold: 0.1,
        is_drifted: true,
        top_drifts: [],
        recommendation: 'Retrain model'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await (modelMonitorTool.execute as any)('test-id', {
        model_id: 'drifted_model'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.drift_score).toBeLessThan(1.0);
    });
  });
});
