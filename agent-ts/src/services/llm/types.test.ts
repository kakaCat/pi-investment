import { describe, it, expect } from '@jest/globals';
import { LLMError } from './types.js';

describe('LLMError', () => {
  it('携带 kind 与 retryable，且是 Error 实例', () => {
    const e = new LLMError('boom', 'rate_limit', true);
    expect(e.message).toBe('boom');
    expect(e.kind).toBe('rate_limit');
    expect(e.retryable).toBe(true);
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('LLMError');
  });

  it('默认 kind=unknown 且不可重试', () => {
    const e = new LLMError('x');
    expect(e.kind).toBe('unknown');
    expect(e.retryable).toBe(false);
  });
});
