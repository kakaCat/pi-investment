import { describe, test, expect } from '@jest/globals';
import { channelHintFromSessionKey } from './session-factory.js';

describe('channelHintFromSessionKey（A3-T1 渠道接线）', () => {
  test('feishu 渠道 key → feishu hint', () => {
    expect(channelHintFromSessionKey('agent:main:feishu:user123')).toBe('feishu');
  });

  test('web 渠道 key → web hint', () => {
    expect(channelHintFromSessionKey('agent:main:web:session456')).toBe('web');
  });

  test('wake/terminal 等无专属 hint 的渠道 → terminal 默认', () => {
    expect(channelHintFromSessionKey('agent:main:wake:rule29')).toBe('terminal');
    expect(channelHintFromSessionKey('agent:main:terminal:local')).toBe('terminal');
  });

  test('非法 key 不抛——回落 terminal（Channel 层绝不阻断会话创建）', () => {
    expect(channelHintFromSessionKey('not-a-valid-key')).toBe('terminal');
    expect(channelHintFromSessionKey('')).toBe('terminal');
  });
});
