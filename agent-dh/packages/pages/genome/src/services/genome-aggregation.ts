// @pi-investment/dashboard-genome · host 聚合服务
// 只读聚合 genomeDir 下 genome.json + candidates.json → GenomeData（含 C1/C2/C3 一致性核验）。
// 一致性规则与 packages/evolver/src/tools/ValidationGateTool/ValidationGateTool.ts
// runConsistencyCheck() 同源（B 步 F1 哨兵，2026-09-06）：本页即该诊断的日常可视化仪表。
//   C1 孤儿候选：watching 候选 genome_version ∉ genome history（promote/rollback 无依据，登记错乱）
//   C2 未登记版本：history stage==='candidate' 无 candidates.json 对应（registerCandidate 断链，
//                  观察版滞留、gate 无案可裁 —— g16 principles v6 曾滞留 9 天属此类）
//   C3 原子写残留：genomeDir 下 *.tmp（写文件中断痕迹）
// 全部 fs 直读（浏览器经同源 API，不直连本地文件）；异常不 throw → 由字段承载（degraded 语义）。

import * as fs from 'node:fs'
import * as path from 'node:path'
import type {
  CandidateInfo, ConsistencyIssue, GenomeData, GenomeSectionInfo,
  HistoryEntry, SectionLastChange,
} from '../types/index.js'

export interface GenomeAggOptions {
  genomeDir: string
}

const SECTION_IDS = ['constitution', 'principles', 'rules', 'lessons'] as const

interface RawGenome {
  genome_version?: string
  created_at?: string
  updated_at?: string
  sections?: Record<string, { class?: string; version?: number; locked?: boolean; order?: number }>
  history?: RawHistoryEntry[]
}
interface RawHistoryEntry {
  version?: string
  section?: string
  section_version?: number
  parent?: string
  type?: string
  stage?: string
  ts?: string
  reason?: string
  git_commit?: string
  author?: string
}

interface RawCandidate {
  id?: string
  section?: string
  section_version?: number
  genome_version?: string
  baseline_version?: string
  created_at?: string
  observe_until?: string
  status?: string
  mutation_type?: string
  health_check?: { passed?: boolean; checked_at?: string; issues?: string[]; size_delta?: number }
  note?: string
}

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8')) as T
  } catch {
    return null
  }
}

const DAY_MS = 86_400_000

export class GenomeAggregationService {
  private readonly genomeDir: string

  constructor(opts: GenomeAggOptions) {
    this.genomeDir = opts.genomeDir
  }

  async fetchGenomeData(): Promise<GenomeData> {
    const genome = readJson<RawGenome>(path.join(this.genomeDir, 'genome.json'))
    const candidates = readJson<RawCandidate[]>(path.join(this.genomeDir, 'candidates.json')) ?? []
    const now = new Date()

    // ---------- ② 段状态矩阵 ----------
    const sectionsRaw = genome?.sections ?? {}
    const historyAll = (genome?.history ?? []).slice().sort((a, b) => (a.ts ?? '').localeCompare(b.ts ?? '')) // ts 升序 → 最新在尾
    const latestBySection = new Map<string, RawHistoryEntry>()
    for (const h of historyAll) {
      if (h.section) latestBySection.set(h.section, h) // 同 section 后面覆盖 → 留最新
    }
    const sections: GenomeSectionInfo[] = SECTION_IDS.map((id) => {
      const raw = sectionsRaw[id]
      const last = latestBySection.get(id)
      const lastChange: SectionLastChange | undefined = last
        ? {
            genomeVersion: last.version,
            type: last.type,
            ts: last.ts,
            reason: last.reason,
          }
        : undefined
      // 段全文：sections/{id}.md（读失败降级空串，不阻断看板）
      let content = ''
      try {
        content = fs.readFileSync(path.join(this.genomeDir, 'sections', `${id}.md`), 'utf8')
      } catch {
        content = ''
      }
      return {
        id,
        version: raw?.version ?? 0,
        class: raw?.class,
        locked: raw?.locked,
        order: raw?.order,
        content,
        lastChange,
      }
    })

    // ---------- history 谱系（⑤，ts 降序 → 最新在前）----------
    const history: HistoryEntry[] = [...historyAll]
      .reverse()
      .map((h) => ({
        genomeVersion: h.version ?? '',
        section: h.section ?? '',
        sectionVersion: h.section_version ?? 0,
        type: (h.type === 'rollback' || h.type === 'promote' ? h.type : 'update') as HistoryEntry['type'],
        stage: h.stage,
        ts: h.ts ?? '',
        reason: h.reason,
        gitCommit: h.git_commit,
        parent: h.parent,
        author: h.author,
      }))

    // ---------- 一致性核验 C1/C2/C3（与 gate runConsistencyCheck 同规则）----------
    const historyVersions = new Set(historyAll.map((h) => h.version).filter(Boolean))
    const candidateStage = historyAll.filter((h) => h.stage === 'candidate')
    const registeredKeys = new Set(
      candidates
        .filter((c) => c.status && c.status !== 'rejected')
        .map((c) => `${c.section}:${c.genome_version}`),
    )
    const issues: ConsistencyIssue[] = []

    // C1 孤儿候选：watching 候选 genome_version 不在 genome history
    const orphanItems = candidates
      .filter((c) => (c.status === 'watching' || c.status === 'extended') && c.genome_version && !historyVersions.has(c.genome_version))
      .map((c) => ({
        id: c.id,
        section: c.section,
        genomeVersion: c.genome_version,
        ts: c.created_at,
      }))
    issues.push({
      id: 'C1',
      label: 'C1 孤儿候选',
      description: 'watching 候选的 genome_version 在 genome history 中不存在——promote/rollback 无依据（登记错乱）',
      items: orphanItems,
    })

    // C2 未登记版本：history stage=candidate 无 candidates.json 对应（registerCandidate 断链）
    const unregistered = candidateStage
      .filter((h) => !registeredKeys.has(`${h.section}:${h.version}`))
      .map((h) => ({
        section: h.section,
        genomeVersion: h.version,
        sectionVersion: h.section_version,
        ts: h.ts,
        reason: h.reason,
      }))
    issues.push({
      id: 'C2',
      label: 'C2 未登记版本',
      description: 'genome history 标 stage=candidate 但 candidates.json 无登记——观察版滞留、gate 无案可裁（registerCandidate 断链；g16 曾滞留 9 天属此类）',
      items: unregistered,
    })

    // C3 原子写残留
    let tmpFiles: string[] = []
    try {
      tmpFiles = fs.readdirSync(this.genomeDir).filter((f) => f.endsWith('.tmp'))
    } catch {
      tmpFiles = []
    }
    issues.push({
      id: 'C3',
      label: 'C3 原子写残留',
      description: 'genomeDir 下存在 *.tmp——写文件中断痕迹（可能写到一半）',
      items: tmpFiles.map((f) => ({ file: f })),
    })

    const activeIssues = issues.map((iss) => ({ ...iss, items: iss.items })).filter((iss) => iss.items.length > 0)

    // ---------- 候选（④，补进度/到期标记）----------
    const candidateInfos: CandidateInfo[] = candidates
      .filter((c) => c.id && c.genome_version)
      .map((c) => {
        const created = c.created_at ? new Date(c.created_at).getTime() : NaN
        const until = c.observe_until ? new Date(c.observe_until).getTime() : NaN
        const watching = c.status === 'watching'
        const due = watching && !Number.isNaN(until) && now.getTime() > until
        let progress: number | undefined
        let remainingDays: number | undefined
        if (!Number.isNaN(created) && !Number.isNaN(until) && until > created) {
          progress = Math.min(1, Math.max(0, (now.getTime() - created) / (until - created)))
          if (!due) remainingDays = Math.max(0, Math.ceil((until - now.getTime()) / DAY_MS))
        }
        return {
          id: c.id ?? '',
          section: c.section ?? '',
          sectionVersion: c.section_version ?? 0,
          genomeVersion: c.genome_version ?? '',
          baselineVersion: c.baseline_version,
          createdAt: c.created_at ?? '',
          observeUntil: c.observe_until,
          status: c.status ?? 'unknown',
          mutationType: c.mutation_type,
          healthCheck: c.health_check
            ? {
                passed: c.health_check.passed ?? false,
                checkedAt: c.health_check.checked_at,
                issues: c.health_check.issues,
                sizeDelta: c.health_check.size_delta,
              }
            : undefined,
          note: c.note,
          due,
          remainingDays,
          progress,
        }
      })

    return {
      genomeVersion: genome?.genome_version ?? '(文件缺失)',
      createdAt: genome?.created_at ?? '',
      updatedAt: genome?.updated_at ?? '',
      sections,
      candidates: candidateInfos,
      consistency: {
        healthy: activeIssues.length === 0,
        checkedAt: new Date().toISOString(),
        issues: issues,
      },
      history,
      fetchedAt: new Date().toISOString(),
    }
  }
}
