import { afterEach, describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { GenomeRollbackTool } from '../src/tools/GenomeRollbackTool/GenomeRollbackTool';

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

function git(dir: string, ...args: string[]) {
  return execFileSync('git', args, { cwd: dir, encoding: 'utf-8' }).trim();
}

describe('genome_rollback 候选绑定', () => {
  it('复原当前候选并同步 history=rejected', async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'genome-rollback-binding-'));
    dirs.push(dir);
    fs.mkdirSync(path.join(dir, 'sections'));
    git(dir, 'init');
    git(dir, 'config', 'user.email', 'test@example.com');
    git(dir, 'config', 'user.name', 'Test');

    fs.writeFileSync(path.join(dir, 'sections', 'rules.md'), '## R-001 基线\n');
    fs.writeFileSync(path.join(dir, 'genome.json'), JSON.stringify({ sections: {}, history: [] }), 'utf-8');
    git(dir, 'add', '-A');
    git(dir, 'commit', '-m', 'baseline');

    fs.writeFileSync(path.join(dir, 'sections', 'rules.md'), '## R-002 候选\n');
    const data: any = {
      genome_version: 'g2',
      updated_at: new Date().toISOString(),
      sections: { rules: { class: 'evolvable', version: 2, order: 30 } },
      history: [{
        version: 'g2', section: 'rules', section_version: 2, parent: 'g1',
        reason: 'candidate', ts: new Date().toISOString(), author: 'agent', type: 'update', stage: 'candidate',
      }],
    };
    fs.writeFileSync(path.join(dir, 'genome.json'), JSON.stringify(data), 'utf-8');
    git(dir, 'add', '-A');
    git(dir, 'commit', '-m', 'candidate');
    data.history[0].git_commit = git(dir, 'rev-parse', '--short', 'HEAD');
    fs.writeFileSync(path.join(dir, 'genome.json'), JSON.stringify(data), 'utf-8');

    const lockGuard = { acquire: async () => () => undefined };
    const tool = new GenomeRollbackTool(dir, data, lockGuard as any) as any;
    await tool.execute({
      section: 'rules', to_section_version: 1, candidate_genome_version: 'g2', reason: '未改善基线',
    }, {});

    expect(fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8')).toContain('基线');
    const saved = JSON.parse(fs.readFileSync(path.join(dir, 'genome.json'), 'utf-8'));
    expect(saved.history.find((e: any) => e.version === 'g2' && e.type === 'update').stage).toBe('rejected');
    expect(saved.sections.rules.version).toBe(3);
  });
});
