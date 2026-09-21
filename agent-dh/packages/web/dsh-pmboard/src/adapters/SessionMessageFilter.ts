/**
 * 会话消息过滤（REQ-47939a t9）——从 host/classifier.ts 与 host/session-sync.ts 迁出**仍在运行时
 * 使用的三个纯函数**，其余（M2 自动分类机制：SessionSyncService / classifySession* /
 * buildClassify* / normalizeClassifyOutput / extractExplicitId / titleFrom*）已随 host/ 一同删除
 * ——它们自 2026-09 起不再被装配（src/index.ts 注释："M2 的自动分类 LLM（SessionSyncService）
 * 自 2026-09 起不再装配（修正 #1/#3：无第二 LLM、人在 loop）"），非测试引用为零。
 *
 * 为什么在 adapters：三个函数都服务于**会话事件 hook** 的输入处理（CaptureHook 判定链的
 * 第 2/4 步），是会话 I/O 边界上的纯文本/元数据规整——与 SessionProbeAdapter 同层。
 *
 * 搬迁口径：函数体逐字保持（含噪声块正则与判据清单），行为零改动。
 *
 * @module dsh-pmboard/adapters/SessionMessageFilter
 */

// ---------------------------------------------------------------------------
// 消息清洗：剔除 harness 注入的系统块（system-reminder / runtime context /
// checkpoint 快照 / 提示词注入等），避免把系统噪声当成对话内容立项。
// （← host/classifier.ts）
// ---------------------------------------------------------------------------

const NOISE_BLOCK_RE = /<system-reminder>[\s\S]*?<\/system-reminder>/g

/** 段落级噪声判据（注入块首行特征）。 */
function isNoiseParagraph(p: string): boolean {
  const s = p.trim()
  if (s.length === 0) return true
  if (/^<system-reminder>/i.test(s)) return true
  if (/^<\/?system-reminder>/.test(s)) return true
  if (/^Current runtime context/i.test(s)) return true
  if (/^Current DSH file policy/i.test(s)) return true
  if (/^Approval prompts? (are|is) disabled/i.test(s)) return true
  if (/^This is an automatically generated checkpoint/i.test(s)) return true
  if (/^\[compacted-summary\]/i.test(s)) return true
  if (/^\[genome:/i.test(s)) return true
  if (/^Treat the captured context/i.test(s)) return true
  if (/^The available skill catalog/i.test(s)) return true
  if (/^Available skills?:/i.test(s)) return true
  if (/^Tool results?[:：]/i.test(s)) return true
  return false
}

/**
 * 清洗用户消息文本：剥掉系统注入块与前置噪声段落，返回真实对话内容。
 * 若整段都是噪声返回空串（调用方应跳过分类，不建 triage 不立项）。
 */
export function cleanUserMessageText(raw: unknown): string {
  if (typeof raw !== 'string') return ''
  let text = raw.replace(NOISE_BLOCK_RE, '')
  // 逐段过滤：保留非噪声、非 markdown 结构标题的段落
  const kept: string[] = []
  for (const para of text.split(/\n{2,}/)) {
    const trimmed = para.trim()
    if (trimmed.length === 0) continue
    if (isNoiseParagraph(trimmed)) continue
    kept.push(trimmed)
  }
  let out = kept.join('\n\n').trim()
  // 进一步剥掉残余的 runtime-context 尾部（同一段内跟在正文后的注入句）
  const ctxIdx = out.search(/Current runtime context/i)
  if (ctxIdx > 20) out = out.slice(0, ctxIdx).trim() // 只当它出现在正文中后部才截断
  return out
}

// ---------------------------------------------------------------------------
// 用户消息文本抽取（← host/session-sync.ts）——从 session/event 的 data 取正文。
// ---------------------------------------------------------------------------

export function extractUserMessageText(msg: unknown): string {
  if (typeof msg !== 'object' || msg === null) return ''
  const content = (msg as { content?: unknown }).content
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content
      .map(part => {
        if (typeof part === 'string') return part
        if (typeof part === 'object' && part !== null && 'text' in part && typeof (part as { text: unknown }).text === 'string') {
          return (part as { text: string }).text
        }
        return ''
      })
      .filter(Boolean)
      .join('\n')
  }
  return ''
}

// ---------------------------------------------------------------------------
// 忽略会话判定（← host/session-sync.ts）——subagent/child/reqboard 内部会话不参与捕获。
// ---------------------------------------------------------------------------

export function isIgnoredSession(sessionId: string, sessionMeta?: unknown): boolean {
  if (sessionId.startsWith('session-reqboard-') || sessionId.startsWith('subagent-') || sessionId.startsWith('child-')) return true
  if (typeof sessionMeta === 'object' && sessionMeta !== null) {
    const s = sessionMeta as { header?: { origin?: string; parentSession?: string; delegationDepth?: number }; meta?: { origin?: string; parentSession?: string; delegationDepth?: number } }
    if (s.header?.origin === 'subagent' || s.meta?.origin === 'subagent') return true
    if (s.header?.parentSession !== undefined || s.meta?.parentSession !== undefined) return true
    if (typeof s.header?.delegationDepth === 'number' && s.header.delegationDepth > 0) return true
    if (typeof s.meta?.delegationDepth === 'number' && s.meta?.delegationDepth > 0) return true
  }
  return false
}
