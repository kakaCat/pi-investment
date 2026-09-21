/**
 * 插件 **dist** 冒烟测试（B8，2026-09-13 w-a9ec14d7）
 *
 * 为什么必须单独存在一份：本仓多数包的 package.json main 指向 **dist/index.mjs**
 * （共 13 个包），而 tests/plugin-schema.smoke.test.ts 只 import 各包的 src 目录——
 * **两者证的不是同一件事**：源码绿灯完全可以在 dist 陈旧 / dist 被清空时依然全绿。
 * 本仓已两次因此误判：
 *   · 改了源码却以为生效（dist 里根本没有新符号，工具从未注册）；
 *   · 构建失败先清空 dist 再报错 → 该插件全部工具濒临消失，退出码之外无人发现。
 * 本测试按**包自己声明的 main**构造插件（与 DSH 加载路径一致），因此：
 *   dist 缺失 / 打包失败 / bundle 不可构造 → 直接失败。
 * ⚠️ 它**不能**证明 dist 与源码同步（陈旧 dist 照样构造成功）——那一层只能靠构建后校验。
 */
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeAll, afterAll } from 'vitest';

let stateDir: string;
beforeAll(() => { stateDir = mkdtempSync(join(tmpdir(), 'plugin-dist-')); });
afterAll(() => rmSync(stateDir, { recursive: true, force: true }));

function stubCtx() {
  return {
    tools: { register: () => () => true, list: () => [] },
    on: () => () => true,
    reflect: { provide: () => {} },
    logger: { info() {}, warn() {}, error() {}, debug() {} },
    genome: { genomeData: { genome_version: 'g1', sections: {} } },
    systemPrompt: { section: () => () => true, variable: () => () => true, assemble: async () => ({ sections: [], tools: [], variables: {} }) },
  } as any;
}

const QV2 = { quantsysV2: { baseURL: 'http://localhost:5001' } };
const AOS = { agentOS: { baseURL: 'local', agentId: 'test' } };

/** 只列 main 指向 dist 的插件（src-main 的包由 plugin-schema.smoke 覆盖） */
const DIST_PLUGINS: Array<[string, () => Promise<any>, () => any]> = [
  ['investment', () => import('../../../packages/tools/investment/dist/index.mjs'), () => QV2],
  ['trading', () => import('../../../packages/tools/trading/dist/index.mjs'), () => QV2],
  ['intelligence', () => import('../../../packages/tools/intelligence/dist/index.mjs'), () => QV2],
  ['competition', () => import('../../../packages/tools/competition/dist/index.mjs'), () => QV2],
  ['market', () => import('../../../packages/tools/market/dist/index.mjs'), () => QV2],
  ['risk', () => import('../../../packages/tools/risk/dist/index.mjs'), () => QV2],
  ['strategy', () => import('../../../packages/tools/strategy/dist/index.mjs'), () => QV2],
  ['factor', () => import('../../../packages/tools/factor/dist/index.mjs'), () => QV2],
  ['data-manager', () => import('../../../packages/tools/data-manager/dist/index.mjs'), () => QV2],
  ['memory', () => import('../../../packages/tools/memory/dist/index.mjs'), () => ({ ...QV2, ...AOS })],
  ['evolution', () => import('../../../packages/tools/evolution/dist/index.mjs'), () => AOS],
  ['scheduler', () => import('../../../packages/tools/scheduler/dist/index.mjs'), () => AOS],
  ['notification', () => import('../../../packages/tools/notification/dist/index.mjs'), () => AOS],
  ['lifecycle', () => import('../../../packages/tools/lifecycle/dist/index.mjs'), () => ({
    repoRoot: '/tmp', agentDhRoot: '/tmp', profileDir: stateDir,
  })],
  ['genome', () => import('../../../packages/tools/genome/dist/index.mjs'), () => ({
    genomeDir: join(stateDir, 'genome-test'),
  })],
];

describe('插件 dist 冒烟（按包声明的 main 构造 = 与 DSH 加载路径一致）', () => {
  for (const [name, load, config] of DIST_PLUGINS) {
    it(`${name} 的 dist 产物可构造`, async () => {
      const mod = await load();
      const Plugin = mod.default;
      expect(typeof Plugin).toBe('function');
      expect(() => new Plugin(stubCtx(), config())).not.toThrow();
    });
  }
});
