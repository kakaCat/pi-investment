import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { findAmbiguousHeadings, findEmptyShellDefs, normalizeRulesContent } from '../src/mergeSection';
import { PromptEvolverTool } from '../src/tools/PromptEvolverTool/PromptEvolverTool';

/**
 * 内容安全回归（2026-09-13，w-adb088f2 —— 来自独立审阅的 3 条发现）
 * #1 delta 合并静默截断正文（含审阅给出的复现输入）
 * #2 损坏标记只覆盖 rules 段
 * #3 空壳规则被当作新增登记
 */

const RULES = ['# 操作规则（可进化）', '', '## R-001 买入前确认', '用 data_fetch_quote 确认当前价格。', '', '## R-002 卖出前确认', '用 position_list 确认可卖数量。', ''].join('\n');
const GOOD_ADD = '## R-016 样本量门槛' + String.fromCharCode(10) + String.fromCharCode(10) + '有效样本 < 7 时不下结论，只登记线索。';

function makeHarness(dir: string, llmText: string, section = 'rules') {
  const calls: Array<{ name: string; args: any }> = [];
  const ctx: any = {
    llm: { stream: () => (async function* () { yield { type: 'text-delta', text: llmText }; })() },
    tools: { execute: async (req: any) => { calls.push({ name: req.name, args: req.arguments }); return { value: { success: true, genome_version: 'g99', new_version: 17, candidate_id: 'cand_x' } }; } },
    genome: { genomeDir: dir },
  };
  return { tool: new PromptEvolverTool(ctx, {} as any, 'p', 'm', 5), calls };
}
function scaffold(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'content-safety-'));
  fs.mkdirSync(path.join(dir, 'sections'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'sections', 'rules.md'), RULES, 'utf-8');
  fs.writeFileSync(path.join(dir, 'sections', 'lessons.md'), '# 经验教训\n\n- 初始条目。\n', 'utf-8');
  return dir;
}

describe('findAmbiguousHeadings（结构歧义）', () => {
  it('空行分隔的正常规则 → 无歧义', () => {
    expect(findAmbiguousHeadings(RULES)).toEqual([]);
  });
  it('审阅复现输入：行内引用被升格为小标题 → 判歧义', () => {
    const cand = '## R-004 复核\n要点：\n## R-001 的执行前提必须已满足\n其余说明。\n';
    const amb = findAmbiguousHeadings(cand);
    expect(amb.length).toBe(1);
    expect(amb[0]).toContain('R-001');
  });
});

describe('findEmptyShellDefs（空壳规则）', () => {
  it('只有标题没有正文 → 判空壳', () => {
    expect(findEmptyShellDefs('## R-009\n')).toEqual(['R-009']);
  });
  it('有正文 → 不判空壳', () => {
    expect(findEmptyShellDefs(GOOD_ADD)).toEqual([]);
  });
});

describe('normalizeRulesContent 暴露丢弃量', () => {
  it('delta 模式报告未落盘的字符数（可见化，不再静默）', () => {
    const poisoned = RULES + '\n' + RULES + '\n## R-016 新规则\n' + String.fromCharCode(10) + '正文内容足够长以保证非空壳。\n';
    const res: any = normalizeRulesContent(RULES, poisoned);
    expect(res.semantics).toBe('delta');
    expect(res.droppedChars).toBeGreaterThan(0);
  });
});

describe('PromptEvolverTool 集成：内容安全 fail-closed', () => {
  const dirs: string[] = [];
  afterEach(() => { for (const d of dirs) fs.rmSync(d, { recursive: true, force: true }); dirs.length = 0; });

  it('#1 歧义候选：拒绝写入，且不调用 genome_update（不再静默截断正文）', async () => {
    const dir = scaffold(); dirs.push(dir);
    const cand = '## R-004 复核' + String.fromCharCode(10) + '要点：' + String.fromCharCode(10) + '## R-001 的执行前提必须已满足' + String.fromCharCode(10) + '其余说明。' + String.fromCharCode(10);
    const h = makeHarness(dir, cand);
    const r: any = await h.tool.call({ suggestions: [{ type: 'strengthen', section: 'rules', content: cand, reason: 't' }], dry_run: false, observe_days: 5 });
    expect(h.calls.filter((c) => c.name === 'genome_update').length).toBe(0);
    expect(r.data.applied_count).toBe(0);
    expect(String(r.data.proposals[0].reason)).toContain('结构歧义');
    expect(fs.readFileSync(path.join(dir, 'sections', 'rules.md'), 'utf-8')).toBe(RULES);
  });

  it('#3 空壳规则：拒绝写入（不再登记空标题占位）', async () => {
    const dir = scaffold(); dirs.push(dir);
    const cand = RULES + String.fromCharCode(10) + '## R-009' + String.fromCharCode(10);
    const h = makeHarness(dir, cand);
    const r: any = await h.tool.call({ suggestions: [{ type: 'strengthen', section: 'rules', content: cand, reason: 't' }], dry_run: false, observe_days: 5 });
    expect(h.calls.filter((c) => c.name === 'genome_update').length).toBe(0);
    expect(String(r.data.proposals[0].reason)).toContain('空壳');
  });

  it('#2 非 rules 段（lessons）的上游建议含 [object Object] → 同样 fail-closed', async () => {
    const dir = scaffold(); dirs.push(dir);
    const h = makeHarness(dir, '一段正常的改写内容，长度足够通过 LLM 输出长度校验。', 'lessons');
    const r: any = await h.tool.call({ suggestions: [{ type: 'strengthen', section: 'lessons', content: '[object Object]', reason: 't' }], dry_run: false, observe_days: 5 });
    expect(h.calls.filter((c) => c.name === 'genome_update').length).toBe(0);
    expect(String(r.data.proposals[0].reason)).toContain('损坏标记');
  });

  it('回归：合法新增规则仍可正常应用（不误伤）', async () => {
    const dir = scaffold(); dirs.push(dir);
    const cand = RULES + String.fromCharCode(10) + GOOD_ADD + String.fromCharCode(10);
    const h = makeHarness(dir, cand);
    const r: any = await h.tool.call({ suggestions: [{ type: 'strengthen', section: 'rules', content: cand, reason: 't' }], dry_run: false, observe_days: 5 });
    const gu = h.calls.filter((c) => c.name === 'genome_update');
    expect(gu.length).toBe(1);
    expect(r.data.applied_count).toBe(1);
    expect(String(gu[0].args.content)).toContain('R-016');
    expect(String(gu[0].args.content)).toContain('有效样本 < 7 时不下结论');
  });
});
