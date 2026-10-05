/**
 * 召回审计端口测试（2026-10-05 重写 · REQ-261004202231-bb99）
 *
 * 主题变化：原实现先 POST quantsys-v2、失败落 JSONL；v2 记忆子系统下线后改为先写 agent-os、
 * 失败落 JSONL。这里**不依赖模块 mock**（本仓 ESM mock 不可靠），改用**假 CLI 脚本**驱动：
 *   - AGENT_OS_CLI_PATH 指向临时脚本 → 由它决定成功/失败，并把收到的参数落盘供断言
 *   - PI_INVEST_DIR 指向临时目录 → JSONL 回退的落点
 * 三条路径：① 成功写 agent-os ② agent-os 失败 → JSONL ③ 两条都失败 → 不抛错
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, rmSync, existsSync, readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { createRecallAuditPort } from './audit-agent-os-client.js';

let tempDir: string;
let fakeCli: string;
let argsFile: string;

const decision = {
  ts: '2026-10-05T09:00:00Z',
  sessionId: 'sess-1',
  flow: 'chat',
  queryText: '查询 600519',
  strategy: 'bm25',
  degraded: false,
  gateResult: 'passed',
  suppressReason: undefined,
  hits: [{ memoryId: 7, score: 0.9, source: 'bm25', bm25Score: 0.9, vectorScore: undefined }],
} as any;

beforeEach(() => {
  tempDir = mkdtempSync(join(tmpdir(), 'recall-audit-test-'));
  fakeCli = join(tempDir, 'fake-agent-os');
  argsFile = join(tempDir, 'cli-args.txt');
  process.env.PI_INVEST_DIR = tempDir;
});

afterEach(() => {
  delete process.env.AGENT_OS_CLI_PATH;
  delete process.env.PI_INVEST_DIR;
  if (tempDir) rmSync(tempDir, { recursive: true, force: true });
});

/** 造一个假 CLI：把收到的参数写入 argsFile，并按 exitCode/输出 模拟成功或失败 */
function makeFakeCli(script: string) {
  writeFileSync(fakeCli, script, { mode: 0o755 });
  process.env.AGENT_OS_CLI_PATH = fakeCli;
}

describe('createRecallAuditPort（agent-os 版）', () => {
  it('正常路径：把决策作为一条 recall-audit 记忆写进 agent-os，且不再落 JSONL', async () => {
    makeFakeCli(`#!/bin/bash
printf "%s " "$@" > "${argsFile}"
echo '{"id":"mem-1"}'
exit 0
`);

    await createRecallAuditPort().record(decision);

    const args = readFileSync(argsFile, 'utf-8');
    expect(args).toContain('memory write');
    expect(args).toContain('recall-audit');
    expect(args).toContain('sess-1');
    expect(existsSync(join(tempDir, 'recall-audit.jsonl'))).toBe(false);
  });

  it('agent-os 失败：回退 JSONL（文件被创建且含该条决策）', async () => {
    makeFakeCli('#!/bin/bash\necho "boom" >&2\nexit 1\n');

    await createRecallAuditPort().record(decision);

    const jsonlPath = join(tempDir, 'recall-audit.jsonl');
    expect(existsSync(jsonlPath)).toBe(true);
    expect(readFileSync(jsonlPath, 'utf-8')).toContain('sess-1');
  });

  it('两条路都失败：不抛错（fire-and-forget 契约）', async () => {
    makeFakeCli('#!/bin/bash\nexit 1\n');
    // JSONL 也写不进去：父目录不存在 → appendFile 报错
    process.env.PI_INVEST_DIR = join(tempDir, 'nope', 'deeper');

    await expect(createRecallAuditPort().record(decision)).resolves.toBeUndefined();
  });
});
