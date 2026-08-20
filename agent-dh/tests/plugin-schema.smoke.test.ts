/**
 * 插件 schema 冒烟测试：用 stub ctx 构造每个插件。
 * defineTool 在注册时即编译 schema（dsh-tools rc7 起要求每个 object 节点显式声明
 * additionalProperties: true|false），构造失败 = DSH 启动时该插件必崩。
 * 新增插件必须加进 PLUGINS 列表。
 */
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeAll, afterAll } from 'vitest';

let stateDir: string;
beforeAll(() => { stateDir = mkdtempSync(join(tmpdir(), 'plugin-smoke-')); });
afterAll(() => rmSync(stateDir, { recursive: true, force: true }));

function stubCtx() {
  return {
    tools: { register: () => () => true },
    on: () => () => true,
    reflect: { provide: () => {} },
    logger: { info() {}, warn() {}, error() {}, debug() {} },
  } as any;
}

const QV2 = { quantsysV2: { baseURL: 'http://localhost:5001' } };
const AOS = { agentOS: { baseURL: 'local', agentId: 'test' } };

const PLUGINS: Array<[string, () => Promise<any>, () => any]> = [
  ['investment', () => import('../packages/investment/src/index.js'), () => QV2],
  ['trading', () => import('../packages/trading/src/index.js'), () => QV2],
  ['intelligence', () => import('../packages/intelligence/src/index.js'), () => QV2],
  ['competition', () => import('../packages/competition/src/index.js'), () => QV2],
  ['market', () => import('../packages/market/src/index.js'), () => QV2],
  ['risk', () => import('../packages/risk/src/index.js'), () => QV2],
  ['strategy', () => import('../packages/strategy/src/index.js'), () => QV2],
  ['factor', () => import('../packages/factor/src/index.js'), () => QV2],
  ['model', () => import('../packages/model/src/index.js'), () => QV2],
  ['data-manager', () => import('../packages/data-manager/src/index.js'), () => QV2],
  ['memory', () => import('../packages/memory/src/index.js'), () => ({ ...QV2, ...AOS })],
  ['evolution', () => import('../packages/evolution/src/index.js'), () => AOS],
  ['scheduler', () => import('../packages/scheduler/src/index.js'), () => AOS],
  ['notification', () => import('../packages/notification/src/index.js'), () => AOS],
  ['lifecycle', () => import('../packages/lifecycle/src/index.js'), () => ({
    repoRoot: '/tmp', agentDhRoot: '/tmp', profileDir: stateDir,
  })],
  ['genome', () => import('../packages/genome/src/index.js'), () => ({
    genomeDir: join(stateDir, 'genome-test'),
  })],
  ['evolver', () => import('../packages/evolver/src/index.js'), () => ({})],
  ['learning', () => import('../packages/learning/src/index.js'), () => QV2],
];

describe('插件 schema 冒烟（构造即编译所有工具 schema）', () => {
  for (const [name, load, config] of PLUGINS) {
    it(`${name} 插件可构造（所有工具 schema 合法）`, async () => {
      const mod = await load();
      const Plugin = mod.default;
      expect(() => new Plugin(stubCtx(), config())).not.toThrow();
    });
  }
});
