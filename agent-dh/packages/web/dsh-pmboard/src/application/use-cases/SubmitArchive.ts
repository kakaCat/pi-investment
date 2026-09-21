/**
 * SubmitArchive 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineArchiveSubmitTool / reqboard_archive_submit 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/SubmitArchive
 */
import type { UseCaseDeps } from '../ports.js'
import {
  ARCHIVE_DOC_RULES,
  assertArchiveMaterials,
  normalizeText,
} from '../../shared/protocol.js'
import { registerArtifact } from '../internal/artifact-gates.js'
import { assertArtifactOpenable } from '../internal/content-gate-wiring.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
} from '../internal/support.js'

export async function submitArchive(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as {
        requirement_id?: unknown
        dir?: unknown
        docs?: unknown
        merged_into?: unknown
        index_entry?: unknown
        manual_updates?: unknown
        manual_note?: unknown
      }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const dir = normalizeText(a.dir, 'dir', 400)
      const indexEntry = normalizeText(a.index_entry, 'index_entry', 1000)
      const kinds = ['requirement', 'plan', 'verification', 'retro', 'notes'] as const
      if (!Array.isArray(a.docs)) reject('reqboard_archive_submit 未执行：docs 必须是数组', 'REQBOARD_INVALID_INPUT')
      const docs = (a.docs as unknown[]).map(d => {
        const o = (typeof d === 'object' && d !== null ? d : {}) as Record<string, unknown>
        const path = normalizeText(o.path, 'docs[].path', 400)
        const rawKind = typeof o.kind === 'string' ? o.kind : ''
        const kind = (kinds as readonly string[]).includes(rawKind) ? (rawKind as (typeof kinds)[number]) : undefined
        if (kind === undefined) {
          reject('reqboard_archive_submit 未执行：docs[].kind 必须是 ' + kinds.join(' / '), 'REQBOARD_INVALID_INPUT')
        }
        if (path.length === 0) reject('reqboard_archive_submit 未执行：docs[].path 不能为空', 'REQBOARD_INVALID_INPUT')
        return { kind, path }
      })
      if (!Array.isArray(a.merged_into)) {
        reject('reqboard_archive_submit 未执行：merged_into 必须是数组', 'REQBOARD_INVALID_INPUT')
      }
      const mergedInto = (a.merged_into as unknown[])
        .map(m => normalizeText(m, 'merged_into[]', 400))
        .filter(m => m.length > 0)
        .slice(0, 10)
      const manualUpdates = Array.isArray(a.manual_updates)
        ? (a.manual_updates as unknown[]).map(u => {
          const o = (typeof u === 'object' && u !== null ? u : {}) as Record<string, unknown>
          return {
            path: normalizeText(o.path, 'manual_updates[].path', 400),
            section: normalizeText(o.section, 'manual_updates[].section', 200),
            summary: normalizeText(o.summary, 'manual_updates[].summary', 500),
          }
        })
        : []
      const manualNote = normalizeText(a.manual_note, 'manual_note', 500)

      // 归档的对象是**已完成**的需求——它已经不在 open 集合里，所以这里按「本窗口的需求」
      // （sourceSessionId 锚点）判定，而不是按 open 判定（否则归档永远找不到自己的需求）。
      const snapshot = deps.repo.snapshot()
      const mine = snapshot.requirements.filter(r => r.sourceSessionId === windowKey)
      if (mine.length === 0) reject('reqboard_archive_submit 未执行：本窗口没有需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0
        ? mine.find(r => r.id === explicitId)
        : [...mine].sort((a, b) => b.updatedAt - a.updatedAt)[0]
      if (target === undefined) {
        reject('reqboard_archive_submit 未执行：需求 ' + explicitId + ' 不是本窗口的需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      const actual = target
      // REQ-9f4a44：验收通过即 archived（归档自动化）——材料在 archived 下补齐；
      // `done` 为 legacy 兼容（历史需求仍可补材料，不被卡死）。
      if (actual.status !== 'archived' && actual.status !== 'done') {
        reject(
          'reqboard_archive_submit 未执行：需求处于 ' + actual.status
          + '，只有已归档（archived）或历史完成（done）的需求才能备归档材料',
          'REQBOARD_BAD_STATUS',
        )
      }
      try {
        assertArchiveMaterials(actual.category, {
          dir, docs, mergedInto, indexEntry,
          ...(manualUpdates.length > 0 ? { manualUpdates } : {}),
          ...(manualNote.length > 0 ? { manualNote } : {}),
        })
      } catch (err) {
        reject('reqboard_archive_submit 未执行：' + ((err as Error).message ?? String(err)), 'REQBOARD_INVALID_INPUT')
      }
      // REQ-2d1c74 FR-5：归档目录与清单内文档登记前可打开性校验——
      // 不存在的目录/文档路径当场拒（REQBOARD_FILE_MISSING），伪路径/越界报 REQBOARD_ARTIFACT_NOT_OPENABLE。
      const openDir = assertArtifactOpenable(deps.docs, dir)
      for (const d of docs) assertArtifactOpenable(deps.docs, d.path)

      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === actual.id)
        if (req === undefined) return undefined
        req.archive = {
          dir: openDir, docs, mergedInto, indexEntry,
          ...(manualUpdates.length > 0 ? { manualUpdates } : {}),
          ...(manualNote.length > 0 ? { manualNote } : {}),
          submittedAt: nowTs,
          submittedBy: { kind: 'agent', sessionId: windowKey },
        }
        // REQ-9f4a44：材料补齐即归档收尾——写 archivePath（原"人点归档"承担的落章动作）
        if (req.status === 'archived') req.archivePath = openDir
        req.comments.push({
          id: deps.ids.comment(),
          body: '[归档] 材料已备（REQ-9f4a44：验收通过即自动归档，此步为材料补齐）：' + dir
            + '\n文档：' + docs.map(d => d.kind + '=' + d.path).join('；')
            + '\n合并进：' + mergedInto.join('；')
            + '\n索引：' + indexEntry
            + (manualUpdates.length > 0
              ? '\n说明书更新：' + manualUpdates.map(u => u.path + '#' + u.section + '（' + u.summary + '）').join('；')
              : (manualNote.length > 0 ? '\n说明书更新：无（' + manualNote + '）' : '')),
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        return { requirements: [req] }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_archive_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：archive 产物 ───────────────────────────
      await deps.repo.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === changed.id)
        if (r === undefined) return undefined
        registerArtifact(r, {
          stage: 'done', kind: 'archive', path: openDir,
          registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
        })
        return { requirements: [r] }
      })
      // 归档漏登警告（REQ-2e9473 t12/W4）：需求目录里存在但未列入归档清单的文件 → 提示，
      // 不硬拦（归档材料可能有意只收关键文档），但让漏登可见（事故 E 的归档侧变体）。
      const archiveDocs = deps.docs
      // 相对路径递归（REQ-47939a t6：不 import node:path，DocRepository.list 自己 resolve）。
      const reqRootRel = 'docs/requirements/' + changed.id
      const listedPaths = new Set(docs.map(d => d.path))
      const unlisted: string[] = []
      const walk = (relDir: string, rel: string): void => {
        // 文档仓储的 list 已吞掉"目录不存在/不可读"（返回 []）——原 try/catch 语义等价。
        for (const entry of archiveDocs.list(relDir)) {
          if (entry.name.startsWith('.')) continue
          const relPath = rel.length > 0 ? rel + '/' + entry.name : entry.name
          if (!entry.isFile) { walk(relDir + '/' + entry.name, relPath); continue }
          const workspacePath = reqRootRel + '/' + relPath
          if (!listedPaths.has(workspacePath) && !listedPaths.has(relPath)) unlisted.push(workspacePath)
        }
      }
      walk(reqRootRel, '')
      return {
        success: true,
        requirement_id: changed.id,
        status: changed.status,
        required_docs: [...(ARCHIVE_DOC_RULES[actual.category ?? 'feature'].requiredDocs)],
        ...(unlisted.length > 0
          ? { unlisted_files: unlisted, warning: '⚠️ 需求目录内有 ' + unlisted.length + ' 个文件未列入归档清单：' + unlisted.slice(0, 8).join('、') + (unlisted.length > 8 ? ' 等' : '') }
          : {}),
        note: '归档材料已备齐并登记（ACCEPT→ARCHIVED 已自动完成，无需人工点归档）'
          + (unlisted.length > 0 ? '；另有 ' + unlisted.length + ' 个目录内文件未列入清单（见 warning/unlisted_files）' : ''),
      }
    }
