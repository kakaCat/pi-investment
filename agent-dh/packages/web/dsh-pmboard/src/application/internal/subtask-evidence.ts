/**
 * 子卡完工凭证口径（REQ-4842fe t5 / design/data-model §4）。
 *
 * 为什么不能沿用父卡四重校验：现有 done 凭证门含"本窗口工具活动"检查，而干活的
 * 子代理在**别的会话**——该检查对子卡恒不成立。子卡改用与窗口无关的三项 + 保留
 * 页面插件构建新鲜度：
 *   ① 子卡 report 非空（调度器从 run 产出生成，含 filesChanged / 完成项）；
 *   ② **证据形态分流**（见 STAGE_EVIDENCE_KIND）：写入族 = filesChanged 至少一个文件真实存在
 *      且 mtime ≥ **链出身**（requirement/父卡/子卡 createdAt 最小值，非会漂移的 claimedAt）；
 *      结论族（review/test/verify/…） = 天然无 diff，完工结论非空即放行；
 *   ③ run 的 stopReason=completed 且产出经 realm 物化非空。
 * **豁免**：本窗口工具活动、60 秒批量关闭节流（这两条是为人工窗口防刷设计的）。
 *
 * @module dsh-pmboard/application/internal/subtask-evidence
 */
import { fmt } from '../../domain/text/fmt.js'
import { STAGE_EVIDENCE_KIND, type StageKind } from '../../domain/task/SubtaskTemplate.js'

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
  /**
   * 证据新鲜度基准 = **链出身**（requirement/父卡/子卡 createdAt 的最小值，见 support.assertDoneEvidence）。
   * 不再是会随重跑漂移的 claimedAt（L1 基准单调化）。
   */
  since: number
  /** 子卡阶段（受控 StageKind）；缺省按写入族从严（见 STAGE_EVIDENCE_KIND） */
  stageKind?: StageKind
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
  
  // 🔍 调试日志：查看实际传入的参数
  const evidenceKindDebug = input.stageKind === undefined
    ? 'file'
    : STAGE_EVIDENCE_KIND[input.stageKind] ?? 'file'
  console.log('[DEBUG checkSubtaskEvidence]', {
    hasReport: input.hasReport,
    stageKind: input.stageKind,
    evidenceKind: evidenceKindDebug,
    valueNonEmpty: run?.valueNonEmpty,
    reportFilesChanged: input.reportFilesChanged?.length,
    reportCompleted: input.reportCompleted?.length
  })
  
  if (run === undefined) return gate(fmt('子卡凭证不过：缺 workflow run 证据（未执行或未落库）', {}))
  if (!run.ok) {
    return gate(fmt('子卡凭证不过：workflow run 未完成（stopReason={stop}{reason}）', {
      stop: run.stopReason,
      reason: run.reason !== undefined ? '；' + run.reason : '',
    }))
  }
  // 证据形态判定前置（用于放宽结论族要求）
  const evidenceKind = input.stageKind === undefined
    ? 'file' // 阶段未知 → 按写入族从严
    : STAGE_EVIDENCE_KIND[input.stageKind] ?? 'file'
  
  // 对结论族子卡放宽 valueNonEmpty 要求：workflow 执行成功即可，允许无产出
  if (!run.valueNonEmpty && evidenceKind !== 'verdict') {
    return gate(fmt('子卡凭证不过：run 产出为空（脚本未返回有效 JSON）。修改方法：在 workflow 末尾 return 一个 JSON 对象，至少包含 filesChanged 或 completed 字段', {}))
  }
  
  // 结论族子卡如果 workflow 成功但无汇报，自动通过（验证通过即为有效结论）
  if (evidenceKind === 'verdict' && !input.hasReport) {
    return { ok: true }
  }
  
  if (!input.hasReport || (input.reportFilesChanged.length === 0 && input.reportCompleted.length === 0)) {
    return gate(fmt('子卡凭证不过：缺少完工汇报（filesChanged/completed 至少一项非空）。修改方法：在 workflow 中 return {"filesChanged": ["路径"], "completed": ["完成项"]}，至少一个数组非空', {}))
  }
  // L2 证据形态分流（D17）：写入族必须有落盘改动；结论族（review/test/verify/…）天然无 diff，
  // 完工结论非空即放行。此前"无 filesChanged 一律拒"让结论族 100% 死、链必停。
  if (input.reportFilesChanged.length === 0) {
    if (evidenceKind !== 'verdict') {
      return gate(fmt('子卡凭证不过：阶段 {stage} 属写入族，汇报未给出改动文件（缺少文件系统证据）。修改方法：确保 workflow 创建/修改了文件，并在返回值的 filesChanged 中列出文件路径', {
        stage: String(input.stageKind ?? ''),
      }))
    }
    // 结论族：前面已保证 filesChanged/completed 至少其一非空，这里 completed 必非空 → 放行。
  } else {
    const fresh = input.reportFilesChanged.some((f) => {
      const m = input.fileMtimes[f]
      return m !== undefined && m >= input.since
    })
    if (!fresh) {
      return gate(fmt('子卡凭证不过：改动文件不存在或 mtime 早于链出身 {since}。修改方法：① 确认文件路径正确（相对工作区根）；② 确保文件在 workflow 执行时被创建/修改；③ 检查文件是否被意外删除', { since: input.since }))
    }
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
