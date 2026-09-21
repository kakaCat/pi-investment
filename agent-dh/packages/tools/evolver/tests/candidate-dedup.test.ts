import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { readCandidates, registerCandidate } from '../src/candidates';
import { PromptEvolverTool } from '../src/tools/PromptEvolverTool/PromptEvolverTool';

/**
 * 候选登记去重契约测试（2026-09-12，w-adb088f2）
 *
 * 真实故障：同一处 RFC 008 断链被两个窗口在不同层各修一次 ——
 *   evolver 侧  f5c8a0a7 (2026-09-03)：PromptEvolverTool 自行 registerCandidate
 *   genome  侧 3d850ab5 (2026-09-12)：GenomeUpdateTool Step 15.5 也 registerCandidate
 * 二者叠加导致一次 prompt_evolver 变异产出 2 条候选（cand_...354 / cand_...389，相差 35ms，
 * 同 section_version=17、同 genome_version=g30），验证门会重复裁决同一变更。
 *
 * 契约：**一次变异只产生一条候选**。
 */

const RULES = [
  '# 操作规则（可进化）',
  '',
  '## R-001 买入前确认',
  '用 data_fetch_quote 确认当前价格。',
  '',
].join('\n');

const NEW_RULE = '## R-016 样本量门槛\n\n有效样本 < 7 时不下结论。';

function setupGenomeDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'evolver-dedup-'));
  fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'sections', 'rules.md'), RULES, 'utf-8');
  return dir;
}

/**
 * 假 ctx：genome_update 侧忠实复刻 3d850ab5 之后的行为 ——
 * 真写段文件，并按 registers 决定是否自行登记候选 + 回传 candidate_id。
 */
function makeHarness(dir: string, opts: { llmText: string; registers: boolean }) {
  const calls: Array<{ name: string; args: any }> = [];
  const ctx: any = {
    llm: {
      stream: () => (async function* () { yield { type: 'text-delta', text: opts.llmText }; })(),
    },
    tools: {
      execute: async (req: any) => {
        calls.push({ name: req.name, args: req.arguments });
        if (req.name === 'genome_update') {
          fs.writeFileSync(
            path.join(dir, 'sections', req.arguments.section + '.md'),
            req.arguments.content,
            'utf-8',
          );
          let candidate_id: string | undefined;
          if (opts.registers) {
            const rec = registerCandidate({
              genomeDir: dir,
              section: req.arguments.section,
              sectionVersion: 17,
              genomeVersion: 'g99',
              baselineVersion: 'g98',
              observeDays: 5,
              mutationType: 'prompt',
            });
            candidate_id = rec.id;
          }
          return { value: { success: true, genome_version: 'g99', new_version: 17, candidate_id } };
        }
        return { value: {} };
      },
    },
    genome: { genomeDir: dir },
  };
  const tool = new PromptEvolverTool(ctx, {} as any, 'test-provider', 'test-model', 5);
  return { tool, calls };
}

describe('候选登记去重（一次变异只产生一条候选）', () => {
  let dir: string;
  beforeEach(() => { dir = setupGenomeDir(); });
  afterEach(() => { fs.rmSync(dir, { recursive: true, force: true }); });

  it('契约：genome_update 已登记时，prompt_evolver 不再重复登记', async () => {
    const llm = RULES + '\n' + NEW_RULE;
    const h = makeHarness(dir, { llmText: llm, registers: true });
    const res: any = await h.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: RULES + '\n' + NEW_RULE, reason: 'dedup' }],
      dry_run: false,
      observe_days: 5,
    });

    const list = readCandidates(dir);
    expect(list.length).toBe(1);                       // ← 契约：只有一条
    const r0 = res.data.results[0];
    expect(r0.success).toBe(true);
    expect(r0.candidate_id).toBe(list[0].id);          // 透传 genome_update 的登记
    expect(String(r0.message)).toMatch(/genome_update/);
    expect(r0.observe_until).toBeTruthy();             // 观察期从 candidates.json 回填
  });

  it('兼容：genome_update 未回传 candidate_id 时兜底自登记（仍只有一条）', async () => {
    const llm = RULES + '\n' + NEW_RULE;
    const h = makeHarness(dir, { llmText: llm, registers: false });
    const res: any = await h.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: RULES + '\n' + NEW_RULE, reason: 'fallback-reg' }],
      dry_run: false,
      observe_days: 5,
    });

    const list = readCandidates(dir);
    expect(list.length).toBe(1);
    const r0 = res.data.results[0];
    expect(r0.success).toBe(true);
    expect(r0.candidate_id).toBe(list[0].id);
    expect(r0.observe_until).toBeTruthy();
  });

  it('两轮连续变异各自只登记一条（累计 2 条，无重复）', async () => {
    const llm1 = RULES + '\n' + NEW_RULE;
    const h1 = makeHarness(dir, { llmText: llm1, registers: true });
    await h1.tool.call({ suggestions: [{ type: 'strengthen', section: 'rules', content: RULES + '\n' + NEW_RULE, reason: 'r1' }], dry_run: false, observe_days: 5 });
    expect(readCandidates(dir).length).toBe(1);

    const after1 = fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8');
    const llm2 = after1 + '\n' + '## R-017 熔断优先级\n\n风控优先于统计显著性。';
    const h2 = makeHarness(dir, { llmText: llm2, registers: true });
    await h2.tool.call({ suggestions: [{ type: 'strengthen', section: 'rules', content: llm2, reason: 'r2' }], dry_run: false, observe_days: 5 });

    const list = readCandidates(dir);
    expect(list.length).toBe(2);
    expect(new Set(list.map((c) => c.id)).size).toBe(2);
  });
});
