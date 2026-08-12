/**
 * Overflow Patterns Tests
 */
import { describe, it, expect } from '@jest/globals';
import { isOverflowError, getMatchedPattern, formatOverflowError } from '../overflow-patterns.js';

describe('isOverflowError', () => {
  it('should detect Anthropic overflow errors', () => {
    expect(isOverflowError(new Error('request_too_large'))).toBe(true);
    expect(isOverflowError(new Error('prompt is too long'))).toBe(true);
    expect(isOverflowError(new Error('max_tokens 150000 exceeds limit'))).toBe(true);
  });

  it('should detect OpenAI overflow errors', () => {
    expect(isOverflowError(new Error('context length exceeded'))).toBe(true);
    expect(isOverflowError(new Error('context_length_exceeded'))).toBe(true);
    expect(isOverflowError(new Error('maximum context length is 128000'))).toBe(true);
    expect(isOverflowError(new Error('tokens 150000 exceed maximum 128000'))).toBe(true);
    expect(isOverflowError(new Error('input is too long for the model'))).toBe(true);
  });

  it('should detect AWS Bedrock overflow errors', () => {
    expect(isOverflowError(new Error('input token count exceeds the maximum number of input tokens'))).toBe(true);
    expect(isOverflowError(new Error('input exceeds the maximum number of tokens'))).toBe(true);
  });

  it('should detect Google Gemini overflow errors', () => {
    expect(isOverflowError(new Error('token limit exceeded'))).toBe(true);
    expect(isOverflowError(new Error('request size exceeds limit'))).toBe(true);
  });

  it('should detect Ollama overflow errors', () => {
    expect(isOverflowError(new Error('ollama error: context length exceeded'))).toBe(true);
    expect(isOverflowError(new Error('context window 128k exceeded'))).toBe(true);
  });

  it('should detect generic overflow errors', () => {
    expect(isOverflowError(new Error('too many tokens'))).toBe(true);
    expect(isOverflowError(new Error('context window full'))).toBe(true);
    expect(isOverflowError(new Error('context size 150000 too large'))).toBe(true);
    expect(isOverflowError(new Error('input text too long'))).toBe(true);
    expect(isOverflowError(new Error('maximum token limit exceeded'))).toBe(true);
    expect(isOverflowError(new Error('token count 200000 exceeds limit'))).toBe(true);
    expect(isOverflowError(new Error('context buffer overflow'))).toBe(true);
    expect(isOverflowError(new Error('prompt content too long'))).toBe(true);
    expect(isOverflowError(new Error('request payload too large'))).toBe(true);
  });

  it('should not detect non-overflow errors', () => {
    expect(isOverflowError(new Error('invalid API key'))).toBe(false);
    expect(isOverflowError(new Error('network timeout'))).toBe(false);
    expect(isOverflowError(new Error('rate limit exceeded'))).toBe(false);
    expect(isOverflowError(new Error('model not found'))).toBe(false);
  });

  it('should handle string errors', () => {
    expect(isOverflowError('context length exceeded')).toBe(true);
    expect(isOverflowError('some other error')).toBe(false);
  });
});

describe('getMatchedPattern', () => {
  it('should return matched pattern source', () => {
    const error = new Error('context length exceeded');
    const pattern = getMatchedPattern(error);
    expect(pattern).toBeTruthy();
    expect(pattern).toContain('context');
    expect(pattern).toContain('length');
  });

  it('should return null for non-overflow errors', () => {
    const error = new Error('invalid API key');
    const pattern = getMatchedPattern(error);
    expect(pattern).toBeNull();
  });
});

describe('formatOverflowError', () => {
  it('should format overflow error with pattern info', () => {
    const error = new Error('context length exceeded');
    const formatted = formatOverflowError(error, 1);

    expect(formatted).toContain('🗜️');
    expect(formatted).toContain('Context overflow detected');
    expect(formatted).toContain('attempt 1');
    expect(formatted).toContain('context length exceeded');
  });

  it('should handle errors without matched pattern', () => {
    const error = new Error('some weird overflow: context is full');
    const formatted = formatOverflowError(error, 2);

    expect(formatted).toContain('attempt 2');
  });

  it('should truncate long error messages', () => {
    const longMessage = 'context length exceeded ' + 'x'.repeat(300);
    const error = new Error(longMessage);
    const formatted = formatOverflowError(error, 1);

    expect(formatted.length).toBeLessThan(longMessage.length + 100);
  });
});
