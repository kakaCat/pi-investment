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
    tools: { register: () => () => true, list: () => [] },
    on: () => () => true,
    reflect: { provide: () => {} },
    // logger 同时支持两种取用形态：ctx.logger.info(...)（Service 插件）与 ctx.logger(name)（函数插件，
    // 如 dsh-pmboard 的 apply）——后者需要 logger 本身可调用（REQ-4842fe t-a46239 补）。
    logger: Object.assign((_name?: string) => ({ info() {}, warn() {}, error() {}, debug() {} }), { info() {}, warn() {}, error() {}, debug() {} }),
    genome: { genomeData: { genome_version: 'g1', sections: {} } },  // P1: evolver 需要
    // genome 插件在构造函数中注册提示词段（P0-1 起）
    systemPrompt: { section: () => () => true, variable: () => () => true, assemble: async () => ({ sections: [], tools: [], variables: {} }) },
  } as any;
}

const QV2 = { quantsysV2: { baseURL: 'http://localhost:5001' } };
const AOS = { agentOS: { baseURL: 'local', agentId: 'test' } };

const PLUGINS: Array<[string, () => Promise<any>, () => any]> = [
  ['investment', () => import('../packages/tools/investment/src/index.js'), () => QV2],
  ['trading', () => import('../packages/tools/trading/src/index.js'), () => QV2],
  ['intelligence', () => import('../packages/tools/intelligence/src/index.js'), () => QV2],
  ['competition', () => import('../packages/tools/competition/src/index.js'), () => QV2],
  ['market', () => import('../packages/tools/market/src/index.js'), () => QV2],
  ['risk', () => import('../packages/tools/risk/src/index.js'), () => QV2],
  ['strategy', () => import('../packages/tools/strategy/src/index.js'), () => QV2],
  ['factor', () => import('../packages/tools/factor/src/index.js'), () => QV2],
  ['data-manager', () => import('../packages/tools/data-manager/src/index.js'), () => QV2],
  ['memory', () => import('../packages/tools/memory/src/index.js'), () => ({ ...QV2, ...AOS })],
  ['evolution', () => import('../packages/tools/evolution/src/index.js'), () => AOS],
  ['scheduler', () => import('../packages/tools/scheduler/src/index.js'), () => AOS],
  ['notification', () => import('../packages/tools/notification/src/index.js'), () => AOS],
  ['lifecycle', () => import('../packages/tools/lifecycle/src/index.js'), () => ({
    repoRoot: '/tmp', agentDhRoot: '/tmp', profileDir: stateDir,
  })],
  ['genome', () => import('../packages/tools/genome/src/index.js'), () => ({
    genomeDir: join(stateDir, 'genome-test'),
  })],
  ['evolver', () => import('../packages/tools/evolver/src/index.js'), () => ({})],
  ['learning', () => import('../packages/tools/learning/src/index.js'), () => QV2],
  ['quantsys-v2-manager', () => import('../packages/runtime/quantsys-v2-manager/src/index.js'), () => ({})],
  ['agent-os-manager', () => import('../packages/runtime/agent-os-manager/src/index.js'), () => ({})],
  // REQ-4842fe t-a46239：dsh-pmboard 此前不在名单里 → 它新注册的工具 schema 无人编译。
  // dshHome 指到临时目录，避免冒烟读写真实 .dsh-data。
  ['dsh-pmboard', () => import('../packages/web/dsh-pmboard/src/index.js'), () => ({ dshHome: stateDir })],
];

describe('插件 schema 冒烟（构造即编译所有工具 schema）', () => {
  for (const [name, load, config] of PLUGINS) {
    it(`${name} 插件可构造（所有工具 schema 合法）`, async () => {
      const mod = await load();
      // 两种插件形态：类插件（default 类，new 即构造）与函数插件（export apply(ctx, config)）。
      const Plugin = mod.default;
      if (typeof Plugin === 'function') {
        expect(() => new Plugin(stubCtx(), config())).not.toThrow();
        return;
      }
      expect(typeof mod.apply).toBe('function');
      expect(() => mod.apply(stubCtx(), config())).not.toThrow();
    });
  }
});
