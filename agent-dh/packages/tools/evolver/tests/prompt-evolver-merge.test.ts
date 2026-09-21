import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  extractRuleDefs,
  findDuplicateRuleDefs,
  normalizeRulesContent,
  assertNoDamage,
  splitRuleBlocks,
} from '../src/mergeSection';
import { PromptEvolverTool } from '../src/tools/PromptEvolverTool/PromptEvolverTool';

/**
 * prompt_evolver 落盘前归一化 / 增量语义 回归测试（2026-09-12，w-c8cae280）
 *
 * 真实故障：2026-09-12 周度变异 prompt_evolver(dry_run=false) 应用 distilled 建议被
 * genome guard 拒绝 —— 『规则段含重复定义：R-001…R-015』。根因是上游把「整段全文」
 * 当建议回灌，LLM 整段重写后既有规则标题被重复定义。
 *
 * 本测试的核心契约：**连续两轮变异后，段内规则 ID 始终唯一**。
 */

const RULES = [
  '# 操作规则（可进化）',
  '',
  '## R-001 买入前确认',
  '用 data_fetch_quote 确认当前价格。',
  '',
  '## R-002 卖出前确认',
  '用 position_list 确认可卖数量。',
  '',
].join('\n');

const NEW_R016 = '## R-016 样本量门槛\n\n有效样本 < 7 时不下结论。';
const NEW_R017 = '## R-017 熔断优先级\n\n风控优先于统计显著性。';

function setupGenomeDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'evolver-merge-'));
  fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'sections', 'rules.md'), RULES, 'utf-8');
  return dir;
}

/** 用假 ctx 驱动真实工具类：genome_update 侧复刻 guard.ts 同口径守门 + 真写文件（replace） */
function makeHarness(genomeDir: string, llmText: string) {
  const calls: Array<{ name: string; args: any }> = [];
  const ctx: any = {
    llm: {
      stream: () => (async function* () { yield { type: 'text-delta', text: llmText }; })(),
    },
    tools: {
      execute: async (req: any) => {
        calls.push({ name: req.name, args: req.arguments });
        if (req.name === 'genome_update') {
          const dups = findDuplicateRuleDefs(req.arguments.content);
          if (req.arguments.section === 'rules' && dups.length > 0) {
            return { isError: true, error: { message: '规则段含重复定义：' + dups.join(', ') } };
          }
          fs.writeFileSync(
            path.join(genomeDir, 'sections', req.arguments.section + '.md'),
            req.arguments.content,
            'utf-8',
          );
          return { value: { success: true, genome_version: 'g99', new_version: 16 } };
        }
        return { value: {} };
      },
    },
    genome: { genomeDir },
  };
  const tool = new PromptEvolverTool(ctx, {} as any, 'test-provider', 'test-model', 5);
  return { tool, calls };
}

describe('mergeSection 纯函数', () => {
  it('splitRuleBlocks 按定义标题切块，prelude 为首块前内容', () => {
    const { prelude, blocks } = splitRuleBlocks(RULES);
    expect(prelude).toContain('# 操作规则');
    expect(blocks.map((b) => b.id)).toEqual(['R-001', 'R-002']);
    expect(blocks[0].text).toContain('data_fetch_quote');
  });

  it('extractRuleDefs 只认标题行；正文引用不算定义', () => {
    const content = '## R-001 A\n正文提到 R-002 但不是定义\n## R-002 B' ;
    expect(extractRuleDefs(content)).toEqual(['R-001', 'R-002']);
    expect(findDuplicateRuleDefs(content)).toEqual([]);
  });

  it('findDuplicateRuleDefs 抓出重复标题定义', () => {
    const content = '## R-001 A\n## R-002 B\n## R-001 A';
    expect(findDuplicateRuleDefs(content)).toEqual(['R-001']);
  });

  it('assertNoDamage 对 [object Object] fail-closed', () => {
    expect(() => assertNoDamage('正常内容', '测试')).not.toThrow();
    expect(() => assertNoDamage('内容 [object Object] 结尾', '测试')).toThrow(/损坏标记/);
  });

  it('候选含重复定义时走 delta：既有规则以当前段为准，只追加新 ID', () => {
    const poisoned = RULES + '\n' + RULES.replace('用 data_fetch_quote 确认当前价格。', '被改写过的正文') + '\n' + NEW_R016;
    const res = normalizeRulesContent(RULES, poisoned);
    expect(res.semantics).toBe('delta');
    expect(res.addedIds).toEqual(['R-016']);
    expect(res.dedupedIds).toContain('R-001');
    expect(res.droppedRewriteIds).toContain('R-001');
    expect(findDuplicateRuleDefs(res.content)).toEqual([]);
    expect(res.content).toContain('用 data_fetch_quote 确认当前价格。');
    expect(res.content).not.toContain('被改写过的正文');
  });

  it('候选整段合法（无重复、未删既有 ID）时保留 replace 语义', () => {
    const rewritten = RULES.replace('用 data_fetch_quote 确认当前价格。', '强化后的买入前确认正文。') + '\n' + NEW_R016;
    const res = normalizeRulesContent(RULES, rewritten);
    expect(res.semantics).toBe('replace');
    expect(res.addedIds).toEqual(['R-016']);
    expect(res.content).toContain('强化后的买入前确认正文。');
  });

  it('候选删除既有规则 ID 时判为不合法 → delta 合并保住既有规则', () => {
    const removing = '## R-002 卖出前确认\n只剩一条。\n## R-016 新规则' ;
    const res = normalizeRulesContent(RULES, removing);
    expect(res.semantics).toBe('delta');
    expect(res.addedIds).toEqual(['R-016']);
    expect(extractRuleDefs(res.content)).toEqual(['R-001', 'R-002', 'R-016']);
  });

  it('无新增规则 → noop（拒绝生成空更新候选）', () => {
    const res = normalizeRulesContent(RULES, RULES);
    expect(res.noop).toBe(true);
    expect(res.addedIds).toEqual([]);
  });
});

describe('合约：连续两轮变异后段内规则 ID 唯一', () => {
  let dir: string;
  beforeEach(() => { dir = setupGenomeDir(); });
  afterEach(() => { fs.rmSync(dir, { recursive: true, force: true }); });

  it('两轮都吃「整段回灌」污染输入，落盘内容规则 ID 始终唯一', async () => {
    // ── 轮 1：LLM 输出 = 当前段 + 当前段副本 + 新规则（真实故障形态）
    const round1LLM = RULES + '\n' + RULES + '\n' + NEW_R016;
    const h1 = makeHarness(dir, round1LLM);
    const r1: any = await h1.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: RULES + '\n' + NEW_R016, reason: 'round1' }],
      dry_run: false,
      observe_days: 5,
    });
    const g1 = h1.calls.filter((c) => c.name === 'genome_update');
    expect(g1.length).toBe(1);
    expect(findDuplicateRuleDefs(g1[0].args.content)).toEqual([]);
    expect(extractRuleDefs(g1[0].args.content)).toEqual(['R-001', 'R-002', 'R-016']);
    expect(r1.success).toBe(true);
    expect(r1.data.applied_count).toBe(1);
    expect(r1.data.results[0].success).toBe(true);
    expect(r1.data.proposals[0].added_ids).toEqual(['R-016']);

    // ── 轮 2：同样的污染形态再来一次，这次带 R-017
    const after1 = fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8');
    expect(extractRuleDefs(after1)).toEqual(['R-001', 'R-002', 'R-016']);
    const round2LLM = after1 + '\n' + after1 + '\n' + NEW_R017;
    const h2 = makeHarness(dir, round2LLM);
    const r2: any = await h2.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: after1 + '\n' + NEW_R017, reason: 'round2' }],
      dry_run: false,
      observe_days: 5,
    });
    const g2 = h2.calls.filter((c) => c.name === 'genome_update');
    expect(g2.length).toBe(1);
    expect(findDuplicateRuleDefs(g2[0].args.content)).toEqual([]);
    expect(extractRuleDefs(g2[0].args.content)).toEqual(['R-001', 'R-002', 'R-016', 'R-017']);
    expect(r2.data.applied_count).toBe(1);

    // ── 落盘文件本身唯一（最终判决）
    const finalContent = fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8');
    expect(findDuplicateRuleDefs(finalContent)).toEqual([]);
    expect(extractRuleDefs(finalContent)).toEqual(['R-001', 'R-002', 'R-016', 'R-017']);
  });

  it('LLM 输出不可用时回退路径不再裸拼接（仍只新增）', async () => {
    const h = makeHarness(dir, '太短');
    const r: any = await h.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: RULES + '\n' + NEW_R016, reason: 'fallback' }],
      dry_run: false,
      observe_days: 5,
    });
    const g = h.calls.filter((c) => c.name === 'genome_update');
    expect(g.length).toBe(1);
    expect(findDuplicateRuleDefs(g[0].args.content)).toEqual([]);
    expect(extractRuleDefs(g[0].args.content)).toEqual(['R-001', 'R-002', 'R-016']);
    expect(r.data.applied_count).toBe(1);
  });

  it('建议内容含 [object Object] 时 fail-closed：不落盘、不发起 genome_update', async () => {
    const h = makeHarness(dir, RULES + '\n' + NEW_R016);
    const r: any = await h.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: '[object Object]', reason: 'damaged' }],
      dry_run: false,
      observe_days: 5,
    });
    expect(h.calls.filter((c) => c.name === 'genome_update').length).toBe(0);
    expect(r.data.applied_count).toBe(0);
    expect(r.data.proposals[0].action).toBe('error');
    expect(String(r.data.proposals[0].reason)).toMatch(/损坏标记/);
    expect(fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8')).toBe(RULES);
  });

  it('无新规则时拒绝应用（不产生空更新候选）', async () => {
    const h = makeHarness(dir, RULES);
    const r: any = await h.tool.call({
      suggestions: [{ type: 'strengthen', section: 'rules', content: RULES, reason: 'noop' }],
      dry_run: false,
      observe_days: 5,
    });
    expect(h.calls.filter((c) => c.name === 'genome_update').length).toBe(0);
    expect(r.data.results[0].success).toBe(false);
    expect(String(r.data.results[0].message)).toMatch(/无实质变更/);
    expect(r.data.proposals[0].noop).toBe(true);
  });
});
