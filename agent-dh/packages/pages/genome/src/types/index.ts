// @pi-investment/dashboard-genome · 共享类型（host 聚合输出 = client 渲染输入）
// 数据域：~/.dsh-agent-dh/genome/ 下 genome.json + candidates.json（本地文件，无 DB 通道）。
// 结构以真实文件为准（2026-09-06 取证）：
//   genome.json  顶层 { genome_version, created_at, updated_at, sections{constitution|principles|rules|lessons}, history[] }
//                 history 条目 { version:gN, section, section_version, parent?, type:update|rollback|promote,
//                                stage?:'candidate'|'active'（promote 后原条目置 active；普通直写无 stage 键）,
//                                ts, reason, git_commit?, author?, force?, baseline_version? }
//   candidates.json 顶层为数组，条目 { id, section, section_version, genome_version, baseline_version,
//                 created_at, observe_until, status:watching|promoted|rejected|..., mutation_type?, health_check?, note? }

export interface SectionLastChange {
  genomeVersion?: string
  type?: string
  ts?: string
  reason?: string
}

/** 段状态卡（② 段状态矩阵） */
export interface GenomeSectionInfo {
  id: 'constitution' | 'principles' | 'rules' | 'lessons'
  version: number
  class?: string
  locked?: boolean
  order?: number
  lastChange?: SectionLastChange
}

/** 候选（④ 候选生命周期流水线） */
export interface CandidateInfo {
  id: string
  section: string
  sectionVersion: number
  genomeVersion: string
  baselineVersion?: string
  createdAt: string
  observeUntil?: string
  status: string
  mutationType?: string
  healthCheck?: {
    passed: boolean
    checkedAt?: string
    issues?: string[]
    sizeDelta?: number
  }
  note?: string
  /** watching 且已过 observe_until → 待裁决（gate 未裁） */
  due?: boolean
  /** 观察期剩余天数（watching & 未到期） */
  remainingDays?: number
  /** 观察进度 0-1（created→observe_until） */
  progress?: number
}

/** 一致性诊断项（③ C1/C2/C3） */
export interface ConsistencyIssue {
  id: 'C1' | 'C2' | 'C3'
  label: string
  description: string
  items: ConsistencyItem[]
}
export interface ConsistencyItem {
  section?: string
  genomeVersion?: string
  sectionVersion?: number
  ts?: string
  reason?: string
  id?: string
  file?: string
}

/** 谱系时间线条目（⑤） */
export interface HistoryEntry {
  genomeVersion: string
  section: string
  sectionVersion: number
  type: 'update' | 'rollback' | 'promote'
  stage?: string
  ts: string
  reason?: string
  gitCommit?: string
  parent?: string
  author?: string
}

export interface GenomeData {
  genomeVersion: string
  createdAt: string
  updatedAt: string
  sections: GenomeSectionInfo[]
  candidates: CandidateInfo[]
  consistency: {
    healthy: boolean
    checkedAt: string
    issues: ConsistencyIssue[]
  }
  history: HistoryEntry[]
  fetchedAt: string
}

/** 信封外层（routes 统一） */
export interface GenomeApiEnvelope {
  success: boolean
  data?: GenomeData
  error?: string
}
