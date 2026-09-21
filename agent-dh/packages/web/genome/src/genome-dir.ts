// @pi-investment/dashboard-genome · genome 数据目录解析（纯 node，无 cordis/dsh 依赖 → 可单测）
//
// 2026-09-13 REQ-3952b7 立。事故：本页默认值原为硬编码 `~/.dsh-agent-dh/genome`；同日 DSH_HOME 迁移后
// genome 插件改读 `<DSH_DATA_DIR>/genome`（.dsh-data/genome），本页仍读旧 home 的空库 →
// ④候选生命周期流水线空、⑤谱系时间线只剩 4 条 g1，而 ③ 一致性诊断全绿（空库天然自洽）——
// 「数据错了却不报错」的最坏形态，靠人眼看版本号才发现。
//
// 解析链（前者优先）：
//   ① 显式 config.genomeDir          运维显式指定（特殊用途/离线复现）
//   ② 运行中 genome 插件实际目录      运行时单一事实源：页面永远读 agent 真正在用的基因组
//   ③ DSH_GENOME_DIR                 部署级显式覆盖
//   ④ <DSH_DATA_DIR>/genome          现役布局（start.sh 导出 DSH_DATA_DIR）
//   ⑤ <DSH_HOME>/genome              旧布局（DSH_HOME=~/.dsh-agent-dh）
//   ⑥ ~/.dsh-agent-dh/genome         遗留兜底（插件缺席且无 env 时）
//
// source 标签随 API 返回 + 启动日志打印：读的是哪个库、凭什么选的，一眼可见。

import * as os from 'node:os'
import * as path from 'node:path'

export type GenomeDirSource =
  | 'config' | 'genome-plugin' | 'DSH_GENOME_DIR' | 'DSH_DATA_DIR' | 'DSH_HOME' | 'legacy-default'

export interface ResolvedGenomeDir {
  dir: string
  source: GenomeDirSource
}

function expandHome(p: string): string {
  return p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p
}

/**
 * 解析 genome 数据目录。env 可注入以便单测。
 * @param configuredDir 插件 config.genomeDir（显式配置）
 * @param liveDir genome 插件实际目录（见 readGenomeServiceDir；读不到传空串）
 */
export function pickGenomeDir(
  configuredDir: string | undefined,
  liveDir: string | undefined,
  env: NodeJS.ProcessEnv = process.env,
): ResolvedGenomeDir {
  const cfg = configuredDir?.trim()
  if (cfg) return { dir: expandHome(cfg), source: 'config' }
  const live = liveDir?.trim()
  if (live) return { dir: expandHome(live), source: 'genome-plugin' }
  const explicit = env.DSH_GENOME_DIR?.trim()
  if (explicit) return { dir: expandHome(explicit), source: 'DSH_GENOME_DIR' }
  const dataDir = env.DSH_DATA_DIR?.trim()
  if (dataDir) return { dir: path.join(dataDir, 'genome'), source: 'DSH_DATA_DIR' }
  const home = env.DSH_HOME?.trim()
  if (home) return { dir: path.join(home, 'genome'), source: 'DSH_HOME' }
  return { dir: path.join(os.homedir(), '.dsh-agent-dh', 'genome'), source: 'legacy-default' }
}

/**
 * 读 genome 插件（cordis Service 名 genome）实际使用的目录。
 * 该字段在插件内是 TS private（运行时仍是普通属性，可读）；读不到返回空串 →
 * 调用方退回 ③④⑤⑥ 解析链，来源标签不会是 'genome-plugin'，不存在静默读错库。
 */
export function readGenomeServiceDir(svc: unknown): string {
  const d = (svc as { genomeDir?: unknown } | undefined)?.genomeDir
  return typeof d === 'string' ? d : ''
}
