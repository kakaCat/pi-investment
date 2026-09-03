import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import { ValidationGateTool } from '../src/tools/ValidationGateTool/ValidationGateTool';

/**
 * L4-B（2026-09-03，w-8366e526）：验证门 health 防御腿单测。
 * 背景：validation_gate 对文本变异（prompt/rule TEXT）原本无内容质检腿，
 * 只能干等记忆样本——38% 验收/测试噪声与空更新不会被拦截。
 * 本次为 judgeCandidates 增加 L4-B 静态腿防御：
 *   ① health_check.passed=false 的 watching 候选直接 rejected（不浪费回测/观察期）
 *   ② health_check 缺失（null/undefined，旧候选未复核）不借故拒绝——降级走正常裁决
 *   ③ verdict 输出携带 health 摘要字段
 * 通过真实实例化 ValidationGateTool 直调 private judgeCandidates 验证。
 */
describe('validation_gate / judgeCandidates health 防御腿', () => {
  let genomeDir: string;
  let tool: ValidationGateTool;
  let osMemoryMock: { searchMemory: () => Promise<any> };

  const makeCandidate = (overrides: Record<string, any> = {}) => ({
    id: 'cand_test_health_1',
    section: 'lessons',
    section_version: 5,
    genome_version: 'g15',
    baseline_version: 'g14',
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    observe_until: new Date(Date.now() - 1000).toISOString(), // 已过期
    status: 'watching' as const,
    mutation_type: 'prompt' as const,
    ...overrides,
  });

  const writeCandidates = (list: any[]) =>
    writeFileSync(path.join(genomeDir, 'candidates.json'), JSON.stringify(list, null, 2));

  const readCandidates = (): any[] =>
    JSON.parse(readFileSync(path.join(genomeDir, 'candidates.json'), 'utf-8'));

  beforeAll(() => {
    genomeDir = mkdtempSync(path.join(tmpdir(), 'l4b-gate-'));
    mkdirSync(path.join(genomeDir, 'sections'), { recursive: true });
    // candidates.json 存在性由各用例写入；mock OS memory 零样本（裁决会走 extended/rejected 分支）
    osMemoryMock = { searchMemory: async () => ({ items: [] }) };

    const ctx = {
      genome: { genomeDir },
      tools: { execute: async () => { throw new Error('不应调用 strategy_execute（health 防御在前）'); } },
    } as any;
    tool = new ValidationGateTool(ctx, osMemoryMock as any, 5);
  });

  afterAll(() => {
    rmSync(genomeDir, { recursive: true, force: true });
  });

  const runGate = async () => (tool as any).judgeCandidates(true, 1); // force=true 跳过过期检查

  it('health_check.passed=false → 直接 rejected，不进入回测/观察门', async () => {
    writeCandidates([makeCandidate({
      health_check: {
        passed: false,
        checked_at: new Date().toISOString(),
        issues: [{ code: 'empty_update', message: '与基线去空白后完全相同：无实质内容变更（空更新/噪声候选）' }],
        size_delta: 0,
        substantive: false,
      },
    })]);
    const verdicts = await runGate();
    expect(verdicts).toHaveLength(1);
    expect(verdicts[0].verdict).toBe('rejected');
    expect(verdicts[0].health_passed).toBe(false);
    expect(verdicts[0].health_issues.join(';')).toContain('空更新');
    expect(readCandidates()[0].status).toBe('rejected');
    expect(readCandidates()[0].note).toContain('L4-B 结构复核拒绝');
  });

  it('health_check 缺失（旧候选未复核）→ 不借故拒绝，降级走正常零样本延期', async () => {
    writeCandidates([makeCandidate()]);  // 无 health_check 字段（模拟 L4-B 前登记的候选）
    const verdicts = await runGate();
    expect(verdicts).toHaveLength(1);
    expect(verdicts[0].verdict).toBe('extended');  // 零样本 → extended，而非被 health 防御拒绝
    expect(verdicts[0].health_passed).toBeNull();   // 降级标注
    expect(readCandidates()[0].status).toBe('watching');  // 未被误杀
  });

  it('health_check.passed=true → 不被静态腿拦截，走正常裁决（零样本 extended）', async () => {
    writeCandidates([makeCandidate({
      health_check: {
        passed: true,
        checked_at: new Date().toISOString(),
        issues: [],
        size_delta: 42,
        substantive: true,
      },
    })]);
    const verdicts = await runGate();
    expect(verdicts[0].verdict).toBe('extended');   // 正常零样本门
    expect(verdicts[0].health_passed).toBe(true);
  });

  it('force 裁决健康通过候选 + 有样本 → 转正 verdict 携带 health_note/摘要', async () => {
    // 有样本：mock searchMemory 返回经验项
    osMemoryMock.searchMemory = async ({ q }: any) => {
      const isCand = (q || '').includes('g15');
      return {
        items: [
          {
            payload: { genome_context: { genome_version: isCand ? 'g15' : 'g14' } },
            content: JSON.stringify({
              reward: isCand ? 0.2 : -0.1,
              action: { tool: 'portfolio_trade' },
            }),
          },
          {
            payload: { genome_context: { genome_version: isCand ? 'g15' : 'g14' } },
            content: JSON.stringify({
              reward: isCand ? 0.3 : 0.1,
              action: { tool: 'portfolio_trade' },
            }),
          },
        ],
      };
    };
    writeCandidates([makeCandidate({
      health_check: {
        passed: true,
        checked_at: new Date().toISOString(),
        issues: [],
        size_delta: 100,
        substantive: true,
      },
    })]);
    // promote 会调 genome_promote → mock tools.execute
    const toolWithPromote = new ValidationGateTool({
      genome: { genomeDir },
      tools: {
        execute: async ({ name }: any) => {
          if (name === 'genome_promote') return { ok: true };
          throw new Error(`未预期的工具调用 ${name}`);
        },
      },
    } as any, osMemoryMock as any, 5);

    const verdicts = await (toolWithPromote as any).judgeCandidates(true, 1);
    expect(verdicts[0].verdict).toBe('promoted');
    expect(verdicts[0].health_passed).toBe(true);
    expect(verdicts[0].health_note).toBeUndefined();  // 实质变更无警示
  });
});
