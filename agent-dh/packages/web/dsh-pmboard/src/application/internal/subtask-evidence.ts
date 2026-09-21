/**
 * 子卡完工凭证口径（REQ-4842fe t5 / design/data-model §4）。
 *
 * 为什么不能沿用父卡四重校验：现有 done 凭证门含"本窗口工具活动"检查，而干活的
 * 子代理在**别的会话**——该检查对子卡恒不成立。子卡改用与窗口无关的三项 + 保留
 * 页面插件构建新鲜度：
 *   ① 子卡 report 非空（调度器从 run 产出生成，含 filesChanged / 完成项）；
 *   ② filesChanged 至少一个文件真实存在且 mtime ≥ 子卡开工时刻（文件系统证据）；
 *   ③ run 的 stopReason=completed 且产出经 realm 物化非空。
 * **豁免**：本窗口工具活动、60 秒批量关闭节流（这两条是为人工窗口防刷设计的）。
 *
 * @module dsh-pmboard/application/internal/subtask-evidence
 */
import { fmt } from '../../domain/text/fmt.js'

/** run 证据投影（台账 TaskRecord.lastRun 的形状）。 */
export interface SubtaskRunView {
  ok: boolean
  stopReason: string
  valueNonEmpty: boolean
  reason?: string
}

export interface SubtaskEvidenceInput {
  hasReport: boolean
  reportFilesChanged: readonly string[]
  reportCompleted: readonly string[]
  run: SubtaskRunView | undefined
  /** 子卡开工时刻（claimedAt；缺省 createdAt） */
  since: number
  /** 汇报文件的 mtime（不存在的文件为 undefined） */
  fileMtimes: Readonly<Record<string, number | undefined>>
  /** 汇报里涉及的页面插件源文件（packages/pages 下 src，构建新鲜度检查用） */
  pagesSrcFiles: readonly string[]
  clientBuildExists: boolean
  clientBuildMtime: number
  newestPagesSrcMtime: number
}

export type EvidenceVerdict = { ok: true } | { ok: false; code: string; reason: string }

const GATE = 'REQBOARD_SUBTASK_GATE'

function gate(reason: string): EvidenceVerdict {
  return { ok: false, code: GATE, reason }
}

/** 三项校验 + 构建新鲜度（保留）；不通过返回 {ok:false}，由调用方拒绝转移。 */
export function checkSubtaskEvidence(input: SubtaskEvidenceInput): EvidenceVerdict {
  const run = input.run
  if (run === undefined) return gate(fmt('子卡凭证不过：缺 workflow run 证据（未执行或未落库）', {}))
  if (!run.ok) {
    return gate(fmt('子卡凭证不过：workflow run 未完成（stopReason={stop}{reason}）', {
      stop: run.stopReason,
      reason: run.reason !== undefined ? '；' + run.reason : '',
    }))
  }
  if (!run.valueNonEmpty) return gate(fmt('子卡凭证不过：run 产出为空（脚本未返回有效 JSON）', {}))
  if (!input.hasReport || (input.reportFilesChanged.length === 0 && input.reportCompleted.length === 0)) {
    return gate(fmt('子卡凭证不过：缺少完工汇报（filesChanged/completed 至少一项非空）', {}))
  }
  if (input.reportFilesChanged.length === 0) {
    return gate(fmt('子卡凭证不过：汇报未给出改动文件（缺少文件系统证据）', {}))
  }
  const fresh = input.reportFilesChanged.some((f) => {
    const m = input.fileMtimes[f]
    return m !== undefined && m >= input.since
  })
  if (!fresh) {
    return gate(fmt('子卡凭证不过：改动文件不存在或 mtime 早于开工时刻 {since}', { since: input.since }))
  }
  if (input.pagesSrcFiles.length > 0) {
    if (!input.clientBuildExists) {
      return gate(fmt('子卡凭证不过：改了 {files} 但 packages/pages/{pkg}/lib/client.js 不存在，请先构建', {
        files: input.pagesSrcFiles.join(', '),
        pkg: pagesPkgOf(input.pagesSrcFiles[0]),
      }))
    }
    if (input.clientBuildMtime < input.newestPagesSrcMtime) {
      return gate(fmt('子卡凭证不过：packages/pages/{pkg}/lib/client.js 旧于 src 最新改动，先重新构建', {
        pkg: pagesPkgOf(input.pagesSrcFiles[0]),
      }))
    }
  }
  return { ok: true }
}

/** 从 pages 源文件路径取包名（构建新鲜度错误消息用）。 */
export function pagesPkgOf(file: string | undefined): string {
  if (file === undefined) return ''
  const m = /^packages\/pages\/([^/]+)\//.exec(file)
  return m?.[1] ?? ''
}

/** 父卡收尾门（INV-5）：存在未 done 子卡时不得收尾。 */
export function checkParentSubtasksDone(subtasks: ReadonlyArray<{ id: string; status: string }>): EvidenceVerdict {
  const open = subtasks.filter((s) => s.status !== 'done' && s.status !== 'canceled')
  if (open.length === 0) return { ok: true }
  return gate(fmt('父卡不能收尾：仍有 {n} 张子卡未完成（{ids}）', {
    n: open.length,
    ids: open.map((s) => s.id).join('、'),
  }))
}
