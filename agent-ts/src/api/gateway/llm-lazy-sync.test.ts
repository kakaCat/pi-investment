import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { createLazyModelSync } from './llm-lazy-sync.js';

describe('createLazyModelSync', () => {
  let currentVersion: number;
  let sync: ReturnType<typeof createLazyModelSync>;

  beforeEach(() => {
    currentVersion = 1;
    sync = createLazyModelSync({
      getVersion: () => currentVersion,
      getSessionModel: () => ({ id: `model-v${currentVersion}` }),
    });
  });

  it('首次调用只记录版本，不 setModel', () => {
    const session = { setModel: jest.fn() };
    sync(session, 'wake:default');
    expect(session.setModel).not.toHaveBeenCalled();
  });

  it('版本变化 → setModel 新模型；再次同版本不重复', () => {
    const session = { setModel: jest.fn() };
    sync(session, 'wake:default');
    currentVersion = 2;
    sync(session, 'wake:default');
    expect(session.setModel).toHaveBeenCalledTimes(1);
    expect(session.setModel).toHaveBeenCalledWith({ id: 'model-v2' });
    sync(session, 'wake:default');
    expect(session.setModel).toHaveBeenCalledTimes(1);
  });

  it('不同 sessionKey 独立跟踪', () => {
    const a = { setModel: jest.fn() };
    const b = { setModel: jest.fn() };
    sync(a, 'wake:a');
    currentVersion = 2;
    sync(a, 'wake:a');
    sync(b, 'wake:b'); // b 首次：只记录
    expect(a.setModel).toHaveBeenCalledTimes(1);
    expect(b.setModel).not.toHaveBeenCalled();
  });

  it('session 无 setModel 方法 → 静默跳过不抛错', () => {
    expect(() => sync({}, 'wake:x')).not.toThrow();
    currentVersion = 2;
    expect(() => sync({}, 'wake:x')).not.toThrow();
  });
});
