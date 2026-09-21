import { describe, it, expect } from 'vitest';
import { promoteCandidate } from '../src/versioning';

/**
 * 转正绑定候选版本回归（2026-09-12，w-adb088f2）
 * 旧行为：promoteCandidate 找『该段最新的 candidate』改 active —— 与裁决对象松耦合。
 * 契约：传入 expectedGenomeVersion 时必须精确命中该条，否则抛错。
 */

const base = (): any => ({
  genome_version: 'g31',
  sections: { rules: { version: 18 }, lessons: { version: 9 } },
  history: [
    { version: 'g29', section: 'lessons', section_version: 9, stage: 'candidate' },
    { version: 'g30', section: 'rules', section_version: 17, stage: 'candidate' },
    { version: 'g31', section: 'rules', section_version: 18, stage: 'candidate' },
  ],
});

describe('promoteCandidate 版本绑定', () => {
  it('指定 genome_version 时精确转正该条，同段其它候选不受影响', () => {
    const out: any = promoteCandidate(base(), 'rules', 'test', undefined, 'g30');
    const g30 = out.history.find((e: any) => e.version === 'g30');
    const g31 = out.history.find((e: any) => e.version === 'g31');
    expect(g30.stage).toBe('active');
    expect(g31.stage).toBe('candidate');
  });

  it('指定版本没有观察中候选 → 抛错（拒绝改错对象）', () => {
    expect(() => promoteCandidate(base(), 'rules', 't', undefined, 'g99')).toThrow(/未找到/);
  });

  it('指定版本存在但已非 candidate → 抛错', () => {
    const g: any = base();
    g.history[1].stage = 'active';
    expect(() => promoteCandidate(g, 'rules', 't', undefined, 'g30')).toThrow(/未找到/);
  });

  it('未指定版本 → 兼容旧行为（该段最新 candidate）', () => {
    const out: any = promoteCandidate(base(), 'rules', 't');
    expect(out.history.find((e: any) => e.version === 'g31').stage).toBe('active');
    expect(out.history.find((e: any) => e.version === 'g30').stage).toBe('candidate');
  });

  it('转正后追加谱系记录（type=promote）', () => {
    const out: any = promoteCandidate(base(), 'rules', 'test', 'abc123', 'g30');
    const last = out.history[out.history.length - 1];
    expect(last.type).toBe('promote');
    expect(last.section).toBe('rules');
  });
});
