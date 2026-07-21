/**
 * Session Services 自修复模块 - Unit Tests
 *
 * 目标：任何一环失败都降级而非崩溃
 * - services 创建：主 agentDir 失败 → 默认 agentDir → 最小 stub
 * - session 恢复：文件缺失/损坏 → 全新会话
 *
 * 注意：ts-jest ESM 模式下 jest.mock 不提升，必须使用
 * jest.unstable_mockModule + 动态 import（ESM 标准做法）。
 */
import { describe, it, expect, beforeEach, jest } from '@jest/globals';

jest.unstable_mockModule('../../sdk-facade.js', () => ({
  createAgentSessionServices: jest.fn(),
  getAgentDir: jest.fn(() => '/mock/default-agent-dir'),
  SessionManager: { open: jest.fn() },
}));

jest.unstable_mockModule('fs', () => ({
  existsSync: jest.fn(),
}));

const { createServicesSafely, openSessionManagerSafely } = await import('./session-services.js');
const { createAgentSessionServices, SessionManager } = await import('../../sdk-facade.js');
const { existsSync } = await import('fs');

const mockCreateServices = createAgentSessionServices as jest.MockedFunction<
  (opts: unknown) => Promise<unknown>
>;
const mockSessionManagerOpen = SessionManager.open as jest.MockedFunction<
  (file: string) => unknown
>;
const mockExistsSync = existsSync as unknown as jest.MockedFunction<(p: string) => boolean>;

describe('createServicesSafely', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns SDK services on success', async () => {
    const services = { cwd: '/proj', agentDir: '/mock/default-agent-dir', diagnostics: [] };
    mockCreateServices.mockResolvedValue(services);

    const result = await createServicesSafely('/proj');

    expect(result).toBe(services);
    expect(mockCreateServices).toHaveBeenCalledTimes(1);
    expect(mockCreateServices).toHaveBeenCalledWith({ cwd: '/proj', agentDir: '/mock/default-agent-dir' });
  });

  it('retries with default agentDir when primary fails', async () => {
    const services = { cwd: '/proj', agentDir: '/mock/default-agent-dir', diagnostics: [] };
    mockCreateServices
      .mockRejectedValueOnce(new Error('bad agentDir'))
      .mockResolvedValueOnce(services);

    const result = await createServicesSafely('/proj', '/broken/agent-dir');

    expect(result).toBe(services);
    expect(mockCreateServices).toHaveBeenCalledTimes(2);
    expect(mockCreateServices).toHaveBeenNthCalledWith(1, { cwd: '/proj', agentDir: '/broken/agent-dir' });
    expect(mockCreateServices).toHaveBeenNthCalledWith(2, { cwd: '/proj', agentDir: '/mock/default-agent-dir' });
  });

  it('returns minimal stub instead of throwing when all attempts fail', async () => {
    mockCreateServices.mockRejectedValue(new Error('total failure'));

    const result: any = await createServicesSafely('/proj');

    expect(result.cwd).toBe('/proj');
    expect(result.agentDir).toBe('/mock/default-agent-dir');
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].type).toBe('error');
  });
});

describe('openSessionManagerSafely', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns undefined for non-string input', () => {
    expect(openSessionManagerSafely(undefined)).toBeUndefined();
    expect(openSessionManagerSafely(null)).toBeUndefined();
    expect(openSessionManagerSafely(123)).toBeUndefined();
  });

  it('returns undefined when session file does not exist', () => {
    mockExistsSync.mockReturnValue(false);

    expect(openSessionManagerSafely('/missing/session.jsonl')).toBeUndefined();
    expect(mockSessionManagerOpen).not.toHaveBeenCalled();
  });

  it('returns undefined when session file is corrupt (open throws)', () => {
    mockExistsSync.mockReturnValue(true);
    mockSessionManagerOpen.mockImplementation(() => {
      throw new Error('invalid JSONL');
    });

    expect(openSessionManagerSafely('/corrupt/session.jsonl')).toBeUndefined();
  });

  it('returns session manager when file opens successfully', () => {
    mockExistsSync.mockReturnValue(true);
    const manager = { getSessionFile: () => '/ok/session.jsonl' };
    mockSessionManagerOpen.mockReturnValue(manager);

    expect(openSessionManagerSafely('/ok/session.jsonl')).toBe(manager);
  });
});
