import { describe, it, expect, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { ValidationGateTool } from '../src/tools/ValidationGateTool/ValidationGateTool';

/**
 * 验证门转正绑定候选版本（2026-09-12，w-adb088f2）—— 直接驱动真实 judgeCandidates。
 * 契约：转正调用必须带上 candidate.genome_version，避免改错同段其它候选。
 */

function makeGate(candidate: any, currentVersion: number) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gate-promote-'));
  fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'candidates.json'), JSON.stringify([candidate], null, 2), 'utf-8');
  fs.writeFileSync(
    path.join(dir, 'genome.json'),
    JSON.stringify({ genome_version: 'g31', sections: { rules: { version: currentVersion } } }),
    'utf-8',
  );
  const calls: Array<{ name: string; args: any }> = [];
  const ctx: any = {
    genome: { genomeDir: dir },
    tools: { execute: async (req: any) => { calls.push({ name: req.name, args: req.arguments }); return { value: { success: true } }; } },
  };
  const tool: any = new ValidationGateTool(ctx, {} as any, 5);
  tool.searchRewards = async () => ({ count: 5, avg: 0.0 });
  return { tool, calls, dir };
}

describe('验证门转正绑定候选版本', () => {
  const dirs: string[] = [];
  afterEach(() => { for (const d of dirs) fs.rmSync(d, { recursive: true, force: true }); dirs.length = 0; });

  it('转正调用带 genome_version（不再转正最新那条）', async () => {
    const cand = {
      id: 'cand_promote_test',
      section: 'rules',
      section_version: 17,
      genome_version: 'g30',
      baseline_version: 'g29',
      created_at: new Date().toISOString(),
      observe_until: new Date(Date.now() - 86400000).toISOString(),
      status: 'watching',
      mutation_type: 'prompt',
      health_check: { passed: true, checked_at: new Date().toISOString(), issues: [], size_delta: 100, substantive: true },
    };
    const h = makeGate(cand, 17);
    dirs.push(h.dir);
    const verdicts: any[] = await h.tool.judgeCandidates(true, 1);
    const promote = h.calls.filter((c) => c.name === 'genome_promote');
    expect(promote.length).toBe(1);
    expect(promote[0].args.genome_version).toBe('g30');
    expect(verdicts[0].verdict).toBe('promoted');
  });
});
