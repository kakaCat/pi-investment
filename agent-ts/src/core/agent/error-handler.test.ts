/**
 * Error Handler Tests
 */
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import {
  ErrorSeverity,
  handleAgentError,
  ErrorHandlers,
  withErrorHandling,
  withAsyncErrorHandling
} from './error-handler.js';

describe('Error Handler', () => {
  let consoleWarnSpy;
  let consoleErrorSpy;

  beforeEach(() => {
    consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleWarnSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });

  describe('handleAgentError', () => {
    it('should not log anything for SILENT severity', () => {
      const error = new Error('test error');
      handleAgentError(error, {
        context: 'test context',
        severity: ErrorSeverity.SILENT
      });

      expect(consoleWarnSpy).not.toHaveBeenCalled();
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('should log warning for WARNING severity', () => {
      const error = new Error('test warning');
      handleAgentError(error, {
        context: 'test context',
        severity: ErrorSeverity.WARNING
      });

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('⚠️')
      );
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('test context')
      );
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('test warning')
      );
    });

    it('should log error for RECOVERABLE severity', () => {
      const error = new Error('test recoverable');
      handleAgentError(error, {
        context: 'test context',
        severity: ErrorSeverity.RECOVERABLE,
        logStack: true
      });

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('❌')
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('test context')
      );
    });

    it('should throw for FATAL severity', () => {
      const error = new Error('test fatal');

      expect(() => {
        handleAgentError(error, {
          context: 'test context',
          severity: ErrorSeverity.FATAL
        });
      }).toThrow('test fatal');

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('💥')
      );
    });

    it('should include metadata in logs', () => {
      const error = new Error('test error');
      const metadata = { userId: '123', action: 'test' };

      handleAgentError(error, {
        context: 'test context',
        severity: ErrorSeverity.WARNING,
        metadata
      });

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        '  Metadata:',
        metadata
      );
    });
  });

  describe('ErrorHandlers', () => {
    it('silent should return default value', () => {
      const error = new Error('test');
      const result = ErrorHandlers.silent(error, 'test context', 'default');

      expect(result).toBe('default');
      expect(consoleWarnSpy).not.toHaveBeenCalled();
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('warn should return default value and log warning', () => {
      const error = new Error('test');
      const result = ErrorHandlers.warn(error, 'test context', 42);

      expect(result).toBe(42);
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('recover should return default value and log error', () => {
      const error = new Error('test');
      const result = ErrorHandlers.recover(error, 'test context', []);

      expect(result).toEqual([]);
      expect(consoleErrorSpy).toHaveBeenCalled();
    });

    it('fatal should throw error', () => {
      const error = new Error('test fatal');

      expect(() => {
        ErrorHandlers.fatal(error, 'test context');
      }).toThrow('test fatal');

      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });

  describe('withErrorHandling', () => {
    it('should return function result on success', () => {
      const fn = (a: number, b: number) => a + b;
      const wrapped = withErrorHandling(fn, 'test', ErrorSeverity.RECOVERABLE);

      const result = wrapped(1, 2);
      expect(result).toBe(3);
    });

    it('should return default value on error', () => {
      const fn = () => { throw new Error('test'); };
      const wrapped = withErrorHandling(fn, 'test', ErrorSeverity.RECOVERABLE, 'default');

      const result = wrapped();
      expect(result).toBe('default');
      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });

  describe('withAsyncErrorHandling', () => {
    it('should return promise result on success', async () => {
      const fn = async (a: number, b: number) => a + b;
      const wrapped = withAsyncErrorHandling(fn, 'test', ErrorSeverity.RECOVERABLE);

      const result = await wrapped(1, 2);
      expect(result).toBe(3);
    });

    it('should return default value on error', async () => {
      const fn = async () => { throw new Error('test'); };
      const wrapped = withAsyncErrorHandling(fn, 'test', ErrorSeverity.RECOVERABLE, 'default');

      const result = await wrapped();
      expect(result).toBe('default');
      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });
});
