import { afterEach, describe, expect, it } from 'vitest';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { GenomeUpdateTool } from '../src/tools/GenomeUpdateTool/GenomeUpdateTool';

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

function setup(watching: boolean) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'genome-update-guard-'));
  dirs.push(dir);
  fs.mkdirSync(path.join(dir, 'sections'));
  fs.writeFileSync(path.join(dir, 'sections', 'rules.md'), '## R-001 原规则\n内容\n');
  const data = {
    genome_version: 'g2',
    updated_at: new Date().toISOString(),
    sections: { rules: { class: 'evolvable', version: 2, order: 30 } },
    history: [],
  };
  fs.writeFileSync(path.join(dir, 'genome.json'), JSON.stringify(data), 'utf-8');
  if (watching) {
    fs.writeFileSync(path.join(dir, 'candidates.json'), JSON.stringify([{
      id: 'cand_active_observation',
      section: 'rules',
      section_version: 2,
      genome_version: 'g2',
      baseline_version: 'g1',
      created_at: new Date().toISOString(),
      observe_until: new Date(Date.now() + 86400000).toISOString(),
      status: 'watching',
    }]), 'utf-8');
  }
  const lockGuard = { acquire: async () => () => undefined };
  return { dir, data, tool: new GenomeUpdateTool(dir, data, lockGuard as any) as any };
}

describe('genome_update 观察期护栏', () => {
  it.each(['candidate', 'active'])('存在 watching 候选时拒绝 %s 写入', async stage => {
    const { dir, tool } = setup(true);
    await expect(tool.execute({
      section: 'rules', content: '## R-002 新规则\n内容\n', reason: 'test', stage,
    }, {})).rejects.toThrow('已有观察中候选');
    expect(fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8')).toContain('R-001');
    expect(JSON.parse(fs.readFileSync(path.join(dir, 'genome.json'), 'utf-8')).genome_version).toBe('g2');
  });

  it('candidates.json 损坏时 fail-closed', async () => {
    const { tool, dir } = setup(false);
    fs.writeFileSync(path.join(dir, 'candidates.json'), '{broken');
    await expect(tool.execute({
      section: 'rules', content: '## R-002 新规则\n内容\n', reason: 'test', stage: 'candidate',
    }, {})).rejects.toThrow();
    expect(fs.readFileSync(path.join(dir, 'candidates.json'), 'utf-8')).toBe('{broken');
  });
});
