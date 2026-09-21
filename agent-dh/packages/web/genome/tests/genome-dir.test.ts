/**
 * genome 目录解析回归 — 2026-09-13 w-57873eb8（REQ-3952b7）
 *
 * 背景：本页默认值原为硬编码 `~/.dsh-agent-dh/genome`。2026-09-13 DSH_HOME 迁移后 genome 插件改读
 * `.dsh-data/genome`，本页仍读旧 home 的 g1 空库 —— ④候选流水线空、⑤谱系只剩 4 条，而 ③ 一致性全绿
 * （空库天然自洽，属「数据错了却不报错」）。真库 g35 / 14 候选 / 37 谱系。
 * 本用例锁死解析链优先级，尤其「运行中 genome 插件目录优先于一切 env」——页面与 agent 同源。
 */
import { describe, expect, it } from 'vitest';
import * as os from 'node:os';
import * as path from 'node:path';

import { pickGenomeDir, readGenomeServiceDir } from '../src/genome-dir';

const E = (o: Record<string, string>): NodeJS.ProcessEnv => o as NodeJS.ProcessEnv;

describe('pickGenomeDir：页面读的到底是哪个库', () => {
  it('① 显式 config 最高优先（含 ~ 展开）', () => {
    expect(pickGenomeDir('~/custom/genome', '/live/genome', E({ DSH_DATA_DIR: '/data' })))
      .toEqual({ dir: path.join(os.homedir(), 'custom', 'genome'), source: 'config' });
  });

  it('② 运行中 genome 插件目录压过 env 链（本次事故的正解）', () => {
    expect(pickGenomeDir(undefined, '/Users/x/.dsh-data/genome', E({ DSH_DATA_DIR: '/Users/x/.dsh-data' })))
      .toEqual({ dir: '/Users/x/.dsh-data/genome', source: 'genome-plugin' });
    // env 指向别处也以插件实际目录为准（同源优先于猜测）
    expect(pickGenomeDir(undefined, '/live/genome', E({ DSH_HOME: '/old-home', DSH_DATA_DIR: '/d' })).dir)
      .toBe('/live/genome');
  });

  it('③④⑤ env 链：DSH_GENOME_DIR > DSH_DATA_DIR > DSH_HOME', () => {
    expect(pickGenomeDir(undefined, '', E({ DSH_GENOME_DIR: '/g', DSH_DATA_DIR: '/d', DSH_HOME: '/h' })))
      .toEqual({ dir: '/g', source: 'DSH_GENOME_DIR' });
    expect(pickGenomeDir(undefined, '', E({ DSH_DATA_DIR: '/d', DSH_HOME: '/h' })))
      .toEqual({ dir: path.join('/d', 'genome'), source: 'DSH_DATA_DIR' });
    expect(pickGenomeDir(undefined, '', E({ DSH_HOME: '/h' })))
      .toEqual({ dir: path.join('/h', 'genome'), source: 'DSH_HOME' });
  });

  it('⑥ 插件缺席且无 env 才退回遗留默认，来源如实标注（不冒充 genome-plugin）', () => {
    const r = pickGenomeDir(undefined, '', E({}));
    expect(r.source).toBe('legacy-default');
    expect(r.dir).toBe(path.join(os.homedir(), '.dsh-agent-dh', 'genome'));
  });

  it('空白串视为未配置（不会被空配置短路）', () => {
    expect(pickGenomeDir('   ', '  ', E({ DSH_DATA_DIR: '/d' })).source).toBe('DSH_DATA_DIR');
  });
});

describe('readGenomeServiceDir：跟随 genome 插件', () => {
  it('读到插件实际使用的目录', () => {
    expect(readGenomeServiceDir({ genomeDir: '/live/genome' })).toBe('/live/genome');
  });

  it('字段缺失 / 类型不对 / 服务缺席 → 空串（调用方退回解析链，来源标签可见，不静默读错库）', () => {
    expect(readGenomeServiceDir(undefined)).toBe('');
    expect(readGenomeServiceDir({})).toBe('');
    expect(readGenomeServiceDir({ genomeDir: 42 })).toBe('');
  });
});
