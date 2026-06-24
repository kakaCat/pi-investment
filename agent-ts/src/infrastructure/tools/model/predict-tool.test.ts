/**
 * Model Predict Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockCallQuantSysDaemon = jest.fn<(func: string, args?: Record<string, unknown>) => Promise<string>>();

jest.unstable_mockModule('../../quant/quantsys-daemon-adapter.js', () => ({
  callQuantSysDaemon: mockCallQuantSysDaemon
}));

const { modelPredictTool } = await import('./predict-tool.js');

// Helper to extract text from tool result
function getResponseText(result: any): string {
  return ((result.content[0] as any).text);
}

describe('model_predict tool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Definition', () => {
    it('should have correct name and label', () => {
      expect(modelPredictTool.name).toBe('model_predict');
      expect(modelPredictTool.label).toBe('模型预测');
    });

    it('should have description', () => {
      expect(modelPredictTool.description).toBeDefined();
      expect(modelPredictTool.description.length).toBeGreaterThan(0);
    });

    it('should have execute function', () => {
      expect(modelPredictTool.execute).toBeDefined();
      expect(typeof modelPredictTool.execute).toBe('function');
    });
  });

  describe('Default parameter prediction', () => {
    it('should predict with default model (latest)', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'buy',
        confidence: 0.85,
        model_id: 'latest',
        features: {
          rsi: 45.2,
          macd: 0.15,
          volume_ratio: 1.3
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledTimes(1);
      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('predict_signal_confidence', {
        symbol: '600519',
        model_name: 'latest',
        features: undefined
      });

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('600519');
      expect(response.signal).toBe('buy');
      expect(response.confidence).toBe(0.85);
    });
  });

  describe('Specified model ID', () => {
    it('should predict with specified model_id', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'sell',
        confidence: 0.72,
        model_id: '20260525_120000'
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', {
        symbol: '600519',
        model_id: '20260525_120000'
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('predict_signal_confidence', {
        symbol: '600519',
        model_name: '20260525_120000',
        features: undefined
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.model_id).toBe('20260525_120000');
    });
  });

  describe('Specified features', () => {
    it('should predict with specified features list', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'hold',
        confidence: 0.65,
        features: {
          rsi: 50.0,
          macd: 0.05
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', {
        symbol: '600519',
        features: ['rsi', 'macd']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('predict_signal_confidence', {
        symbol: '600519',
        model_name: 'latest',
        features: ['rsi', 'macd']
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.features).toBeDefined();
      expect(Object.keys(response.features)).toEqual(['rsi', 'macd']);
    });
  });

  describe('A-share prediction', () => {
    it('should predict for A-share stock', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '000001',
        name: '平安银行',
        signal: 'buy',
        confidence: 0.78
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '000001' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('predict_signal_confidence', {
        symbol: '000001',
        model_name: 'latest',
        features: undefined
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('000001');
    });
  });

  describe('HK stock prediction', () => {
    it('should predict for HK stock with .HK suffix', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '9988.HK',
        name: '阿里巴巴-SW',
        signal: 'buy',
        confidence: 0.82
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '9988.HK' });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('predict_signal_confidence', {
        symbol: '9988.HK',
        model_name: 'latest',
        features: undefined
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('9988.HK');
    });

    it('should predict for HK stock without suffix', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '700',
        name: '腾讯控股',
        signal: 'hold',
        confidence: 0.68
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '700' });

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('700');
    });
  });

  describe('Parameter combination tests', () => {
    it('should handle all parameters together', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'buy',
        confidence: 0.88,
        model_id: '20260520_100000',
        features: {
          rsi: 42.5,
          macd: 0.20,
          kdj_k: 35.0
        }
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', {
        symbol: '600519',
        model_id: '20260520_100000',
        features: ['rsi', 'macd', 'kdj_k']
      });

      expect(mockCallQuantSysDaemon).toHaveBeenCalledWith('predict_signal_confidence', {
        symbol: '600519',
        model_name: '20260520_100000',
        features: ['rsi', 'macd', 'kdj_k']
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.symbol).toBe('600519');
      expect(response.model_id).toBe('20260520_100000');
      expect(response.features).toBeDefined();
    });
  });

  describe('Error handling - missing symbol', () => {
    it('should reject when symbol is missing', async () => {
      const result = await (modelPredictTool.execute as any)('test-call-id', {});

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('symbol 参数是必需的');
    });

    it('should reject when symbol is empty string', async () => {
      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('symbol 参数是必需的');
    });

    it('should reject when symbol is whitespace only', async () => {
      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '   ' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('symbol 参数是必需的');
    });
  });

  describe('Error handling - invalid symbol', () => {
    it('should reject US stock symbol', async () => {
      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: 'AAPL' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('不支持的股票代码');
      expect(response.invalid_format).toBe(true);
    });

    it('should reject invalid format', async () => {
      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: 'INVALID123' });

      expect(mockCallQuantSysDaemon).not.toHaveBeenCalled();

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.invalid_format).toBe(true);
    });
  });

  describe('Error handling - model not found', () => {
    it('should handle model not found error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Model not found: 20260101_000000'));

      const result = await (modelPredictTool.execute as any)('test-call-id', {
        symbol: '600519',
        model_id: '20260101_000000'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.model_not_found).toBe(true);
      expect(response.error).toContain('不存在');
      expect(response.error).toContain('model_list');
    });

    it('should handle Chinese model not found error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('模型不存在'));

      const result = await (modelPredictTool.execute as any)('test-call-id', {
        symbol: '600519',
        model_id: 'nonexistent'
      });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.model_not_found).toBe(true);
    });
  });

  describe('Error handling - daemon failure', () => {
    it('should handle daemon connection error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('QuantSys daemon is not running'));

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.daemon_error).toBe(true);
      expect(response.error).toContain('无法连接到量化系统后端');
    });

    it('should handle daemon timeout error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Request timeout after 150000ms'));

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.daemon_error).toBe(true);
      expect(response.error).toContain('无法连接到量化系统后端');
    });

    it('should handle generic daemon error', async () => {
      mockCallQuantSysDaemon.mockRejectedValueOnce(new Error('Python process crashed'));

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('Python process crashed');
    });
  });

  describe('Response format validation', () => {
    it('should return valid JSON response', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'buy',
        confidence: 0.85
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe('text');

      const response = JSON.parse(getResponseText(result));
      expect(typeof response).toBe('object');
      expect(response).not.toBeNull();
    });

    it('should handle invalid JSON response from daemon', async () => {
      mockCallQuantSysDaemon.mockResolvedValueOnce('not valid json');

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      // Should throw during JSON.parse and be caught
      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();
    });

    it('should handle null response from daemon', async () => {
      mockCallQuantSysDaemon.mockResolvedValueOnce('null');

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.success).toBe(false);
      expect(response.error).toContain('无效的响应格式');
    });
  });

  describe('Confidence range validation', () => {
    it('should accept confidence in valid range (0-1)', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'buy',
        confidence: 0.75
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.confidence).toBeGreaterThanOrEqual(0);
      expect(response.confidence).toBeLessThanOrEqual(1);
    });

    it('should handle low confidence prediction', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'hold',
        confidence: 0.15
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.confidence).toBe(0.15);
      expect(response.signal).toBe('hold');
    });

    it('should handle high confidence prediction', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'buy',
        confidence: 0.95
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.confidence).toBe(0.95);
    });
  });

  describe('Prediction signal validation', () => {
    it('should handle buy signal', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'buy',
        confidence: 0.85
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.signal).toBe('buy');
    });

    it('should handle sell signal', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'sell',
        confidence: 0.80
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.signal).toBe('sell');
    });

    it('should handle hold signal', async () => {
      const mockPrediction = JSON.stringify({
        symbol: '600519',
        signal: 'hold',
        confidence: 0.60
      });

      mockCallQuantSysDaemon.mockResolvedValueOnce(mockPrediction);

      const result = await (modelPredictTool.execute as any)('test-call-id', { symbol: '600519' });

      const response = JSON.parse(getResponseText(result));
      expect(response.signal).toBe('hold');
    });
  });
});
