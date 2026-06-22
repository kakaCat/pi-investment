/**
 * Model List Tool Tests - Business Logic Coverage
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

// Create mock function
const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

// Mock quantsys daemon adapter using unstable_mockModule
jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

// Import after mocking
const { modelListTool } = await import('./list-tool.js');

// Helper to extract text from result
const getText = (result: any): string => {
  const content = result.content[0];
  return content.type === 'text' ? content.text : '';
};

describe('modelListTool - Tool Definition', () => {
  it('should have correct tool name', () => {
    expect(modelListTool.name).toBe('model_list');
  });

  it('should have correct label', () => {
    expect(modelListTool.label).toBe('模型列表');
  });

  it('should have description mentioning model listing', () => {
    expect(modelListTool.description).toContain('列出');
    expect(modelListTool.description).toContain('模型');
  });

  it('should have parameters object', () => {
    expect(modelListTool.parameters).toBeDefined();
    expect(typeof modelListTool.parameters).toBe('object');
  });

  it('should have execute function', () => {
    expect(modelListTool.execute).toBeDefined();
    expect(typeof modelListTool.execute).toBe('function');
  });

  it('should have optional status parameter', () => {
    const params = modelListTool.parameters as any;
    expect(params.properties).toBeDefined();
    expect(params.properties.status).toBeDefined();
  });
});

describe('modelListTool - Business Logic', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('listing all models', () => {
    it('should list all models with default parameters', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          },
          {
            model_id: '20260523_150000',
            model_type: 'lightgbm',
            model_path: '/Users/test/.pi-invest/ml/models/lightgbm_model_20260523_150000.pkl',
            timestamp: '2026-05-23T15:00:00',
            test_accuracy: 0.81,
            test_f1: 0.78,
            n_features: 60
          }
        ],
        total: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.models).toBeDefined();
      expect(Array.isArray(response.models)).toBe(true);
      expect(response.total).toBeDefined();
    });

    it('should list all models explicitly', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          },
          {
            model_id: '20260523_150000',
            model_type: 'lightgbm',
            model_path: '/Users/test/.pi-invest/ml/models/lightgbm_model_20260523_150000.pkl',
            timestamp: '2026-05-23T15:00:00',
            test_accuracy: 0.81,
            test_f1: 0.78,
            n_features: 60
          }
        ],
        total: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'all'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.models.length).toBeGreaterThan(1);
      expect(response.total).toBe(3);
    });
  });

  describe('listing latest model only', () => {
    it('should list only latest model when status=latest', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'latest'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.models.length).toBe(1);
      expect(response.total).toBe(1);
      expect(response.models[0].model_id).toBe('20260525_120000');
    });
  });

  describe('model count validation', () => {
    it('should return correct total count', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          },
          {
            model_id: '20260523_150000',
            model_type: 'lightgbm',
            model_path: '/Users/test/.pi-invest/ml/models/lightgbm_model_20260523_150000.pkl',
            timestamp: '2026-05-23T15:00:00',
            test_accuracy: 0.81,
            test_f1: 0.78,
            n_features: 60
          }
        ],
        total: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'all'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.total).toBe(response.models.length);
    });

    it('should handle empty model list', async () => {
      const mockResponse = JSON.stringify({
        models: [],
        total: 0
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'empty'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.models).toEqual([]);
      expect(response.total).toBe(0);
    });
  });

  describe('model fields validation', () => {
    it('should have all required fields in each model', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const model = response.models[0];

      expect(model).toHaveProperty('model_id');
      expect(model).toHaveProperty('model_type');
      expect(model).toHaveProperty('model_path');
      expect(model).toHaveProperty('timestamp');
      expect(model).toHaveProperty('test_accuracy');
      expect(model).toHaveProperty('test_f1');
      expect(model).toHaveProperty('n_features');
    });

    it('should have correct field types', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const model = response.models[0];

      expect(typeof model.model_id).toBe('string');
      expect(typeof model.model_type).toBe('string');
      expect(typeof model.model_path).toBe('string');
      expect(typeof model.timestamp).toBe('string');
      expect(typeof model.test_accuracy).toBe('number');
      expect(typeof model.test_f1).toBe('number');
      expect(typeof model.n_features).toBe('number');
    });
  });

  describe('timestamp format validation', () => {
    it('should have valid ISO timestamp format', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const model = response.models[0];

      // Check ISO 8601 format
      expect(model.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });

    it('should have parseable timestamp', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const model = response.models[0];

      const date = new Date(model.timestamp);
      expect(date.toString()).not.toBe('Invalid Date');
    });
  });

  describe('model path validation', () => {
    it('should have valid model path', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const model = response.models[0];

      expect(model.model_path).toContain('.pi-invest');
      expect(model.model_path).toContain('ml/models');
      expect(model.model_path).toMatch(/\.(pkl|joblib)$/);
    });

    it('should have model_id in path', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const model = response.models[0];

      expect(model.model_path).toContain(model.model_id);
    });
  });

  describe('test metrics validation', () => {
    it('should have accuracy in valid range', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          }
        ],
        total: 2
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));

      response.models.forEach((model: any) => {
        expect(model.test_accuracy).toBeGreaterThanOrEqual(0);
        expect(model.test_accuracy).toBeLessThanOrEqual(1);
      });
    });

    it('should have F1 score in valid range', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          }
        ],
        total: 2
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));

      response.models.forEach((model: any) => {
        expect(model.test_f1).toBeGreaterThanOrEqual(0);
        expect(model.test_f1).toBeLessThanOrEqual(1);
      });
    });

    it('should have positive feature count', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          }
        ],
        total: 2
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));

      response.models.forEach((model: any) => {
        expect(model.n_features).toBeGreaterThan(0);
      });
    });
  });

  describe('error handling', () => {
    it('should handle daemon connection failure', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Daemon connection failed'));

      const result = await modelListTool.execute('test-id', {
        status: 'daemon_error'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('Daemon connection failed');
    });
  });

  describe('response format validation', () => {
    it('should return valid JSON response', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const text = getText(result);
      expect(() => JSON.parse(text)).not.toThrow();
    });

    it('should have models array and total count', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          }
        ],
        total: 1
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {}, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      expect(response).toHaveProperty('models');
      expect(response).toHaveProperty('total');
      expect(Array.isArray(response.models)).toBe(true);
      expect(typeof response.total).toBe('number');
    });
  });

  describe('model type validation', () => {
    it('should support xgboost models', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          },
          {
            model_id: '20260523_150000',
            model_type: 'lightgbm',
            model_path: '/Users/test/.pi-invest/ml/models/lightgbm_model_20260523_150000.pkl',
            timestamp: '2026-05-23T15:00:00',
            test_accuracy: 0.81,
            test_f1: 0.78,
            n_features: 60
          }
        ],
        total: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'all'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const xgboostModels = response.models.filter((m: any) => m.model_type === 'xgboost');
      expect(xgboostModels.length).toBeGreaterThan(0);
    });

    it('should support lightgbm models', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          },
          {
            model_id: '20260523_150000',
            model_type: 'lightgbm',
            model_path: '/Users/test/.pi-invest/ml/models/lightgbm_model_20260523_150000.pkl',
            timestamp: '2026-05-23T15:00:00',
            test_accuracy: 0.81,
            test_f1: 0.78,
            n_features: 60
          }
        ],
        total: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'all'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const lightgbmModels = response.models.filter((m: any) => m.model_type === 'lightgbm');
      expect(lightgbmModels.length).toBeGreaterThan(0);
    });
  });

  describe('model sorting', () => {
    it('should return models in descending timestamp order', async () => {
      const mockResponse = JSON.stringify({
        models: [
          {
            model_id: '20260525_120000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260525_120000.pkl',
            timestamp: '2026-05-25T12:00:00',
            test_accuracy: 0.85,
            test_f1: 0.82,
            n_features: 62
          },
          {
            model_id: '20260524_100000',
            model_type: 'xgboost',
            model_path: '/Users/test/.pi-invest/ml/models/xgboost_model_20260524_100000.pkl',
            timestamp: '2026-05-24T10:00:00',
            test_accuracy: 0.83,
            test_f1: 0.80,
            n_features: 58
          },
          {
            model_id: '20260523_150000',
            model_type: 'lightgbm',
            model_path: '/Users/test/.pi-invest/ml/models/lightgbm_model_20260523_150000.pkl',
            timestamp: '2026-05-23T15:00:00',
            test_accuracy: 0.81,
            test_f1: 0.78,
            n_features: 60
          }
        ],
        total: 3
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockResponse);

      const result = await modelListTool.execute('test-id', {
        status: 'all'
      }, undefined, undefined, {} as any);

      const response = JSON.parse(getText(result));
      const timestamps = response.models.map((m: any) => new Date(m.timestamp).getTime());

      // Check descending order (newest first)
      for (let i = 0; i < timestamps.length - 1; i++) {
        expect(timestamps[i]).toBeGreaterThanOrEqual(timestamps[i + 1]);
      }
    });
  });
});
