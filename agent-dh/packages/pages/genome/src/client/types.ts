/**
 * Client-side types mirroring the host /dashboard/api/genome payload
 * (subset the client renders; single source is src/types/index.ts host-side).
 *
 * @module dashboard-genome/client/types
 */
export interface ApiResponse<T> { success: boolean; data?: T; error?: string }

export interface SectionLastChange {
  genomeVersion?: string
  type?: string
  ts?: string
  reason?: string
}
export interface GenomeSectionInfo {
  id: string
  version: number
  class?: string
  locked?: boolean
  order?: number
  lastChange?: SectionLastChange
}
export interface CandidateHealthCheck {
  passed?: boolean
  checkedAt?: string
  issues?: string[]
  sizeDelta?: number
}
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
  healthCheck?: CandidateHealthCheck
  note?: string
  due?: boolean
  remainingDays?: number
  progress?: number
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
export interface ConsistencyIssue {
  id: string
  label: string
  description: string
  items: ConsistencyItem[]
}
export interface HistoryEntry {
  genomeVersion: string
  section: string
  sectionVersion: number
  type: string
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
  consistency: { healthy: boolean; checkedAt: string; issues: ConsistencyIssue[] }
  history: HistoryEntry[]
  fetchedAt: string
}
