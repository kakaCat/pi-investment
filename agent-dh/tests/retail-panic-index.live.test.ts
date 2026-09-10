/**
 * retail_panic_index 线上端到端核验（默认跳过，LIVE=1 才跑）
 *
 * 背景（2026-09-10，w-23c70356）：后端维度降级时返回 null，旧实现透传 null →
 * 框架 output schema 校验拒绝，工具整体不可用。修复后应"无数据即不出键"。
 * 本测试用**真实 quantsys-v2 后端**跑三个用例，并用与框架同口径的校验器复查，
 * 因此无需重启 DSH profile 即可核实修复在线上数据上成立。
 *
 * 运行：cd agent-dh && LIVE=1 npx vitest run tests/retail-panic-index.live.test.ts
 */
import { describe, it, expect } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { RetailPanicIndexTool } from '../packages/competition/src/tools/RetailPanicIndexTool/RetailPanicIndexTool.js';
import { retailPanicIndexPrompt } from '../packages/competition/src/tools/RetailPanicIndexTool/prompt.js';

const LIVE = process.env.LIVE === '1';
const OUT_SCHEMA: any = (retailPanicIndexPrompt as any).output.schema;

function check(schema: any, value: any, path = 'value', errs: string[] = []): string[] {
  if (value === undefined) return errs;
  if (value === null) { errs.push(`${path} 为 null（schema.type=${schema?.type}）`); return errs; }
  if (schema?.type === 'number' && typeof value !== 'number') errs.push(`${path} 应为 number，实为 ${typeof value}`);
  if (schema?.type === 'string' && typeof value !== 'string') errs.push(`${path} 应为 string，实为 ${typeof value}`);
  if (schema?.type === 'boolean' && typeof value !== 'boolean') errs.push(`${path} 应为 boolean，实为 ${typeof value}`);
  if (schema?.type === 'object') {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const sub = schema.properties?.[k];
      if (!sub) {
        if (schema.additionalProperties !== true) errs.push(`${path}.${k} 未声明且 additionalProperties != true`);
        continue;
      }
      check(sub, v, `${path}.${k}`, errs);
    }
  }
  return errs;
}

describe.skipIf(!LIVE)('retail_panic_index 线上核验（真实后端）', () => {
  const client = new QuantsysV2Client({
    baseURL: process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001',
    timeout: 20000,
  } as any);
  const tool: any = new RetailPanicIndexTool(client);

  for (const [label, args] of [
    ['最新一日（默认）', {}],
    ['指定 2026-09-10', { trade_date: '2026-09-10' }],
    ['序列 days=5', { days: 5 }],
  ] as Array<[string, any]>) {
    it(`${label} 输出通过 output schema 校验`, async () => {
      const res = await tool.execute(args, {});
      // eslint-disable-next-line no-console
      console.log(label, '→', JSON.stringify(res));
      expect(check(OUT_SCHEMA, res)).toEqual([]);
    }, 30000);
  }
});
