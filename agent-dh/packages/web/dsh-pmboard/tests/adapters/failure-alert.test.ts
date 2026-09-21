/**
 * 失败告警适配器契约（REQ-4842fe t8 / FR-13）+「本插件代码不发飞书」不变量。
 *
 * 不变量来源：2026-09-21 用户裁定——本需求的失败告警口径 = 来源会话弹框 + 宿主日志，
 * **不发飞书**（requirement §8 #17、design/observability §3、ports.FailureAlertPort 注释）。
 *
 * 两条纪律：
 *  ① 适配器只走两条通道（宿主日志 + 来源会话投递），且**永不抛**——告警失败不得反过来
 *     阻断暂停与留痕；
 *  ② 全 `src/` 的**可执行代码**不得出现飞书外发面：注释里可以解释「为什么不发」，
 *     代码里一行都不许有——防「口径改了、代码又悄悄接回去」。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createFailureAlert } from '../../src/adapters/FailureAlert.js'

const SRC = fileURLToPath(new URL('../../src', import.meta.url))

function tsFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name)
    if (e.isDirectory()) return tsFiles(p)
    return e.isFile() && e.name.endsWith('.ts') ? [p] : []
  })
}

/** 剥掉注释，只留可执行代码（避免「注释里解释不发飞书」被误判）。 */
function codeOnly(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^[ \t]*\/\/.*$/gm, '')
}

describe('createFailureAlert：两条通道 + 永不抛', () => {
  it('日志与来源会话各写一次，正文含告警内容', () => {
    const logged: string[] = []
    const delivered: Array<{ wk: string; text: string }> = []
    const alert = createFailureAlert({
      log: (m) => logged.push(m),
      deliver: (wk, text) => delivered.push({ wk, text }),
      windowFor: () => 'w-abc',
    })

    alert.alert({ requirementId: 'REQ-4842fe', title: '【实施链暂停】REQ-4842fe', content: '· 可选处置：重跑该卡' })

    expect(logged).toHaveLength(1)
    expect(logged[0]).toContain('【实施链暂停】REQ-4842fe')
    expect(delivered).toHaveLength(1)
    expect(delivered[0]!.wk).toBe('w-abc')
    expect(delivered[0]!.text).toContain('重跑该卡')
  })

  it('投递文本 = 弹框指令壳（§8 #18）：含弹框指令与三处置选项；宿主日志仍是原始正文', () => {
    const logged: string[] = []
    const delivered: Array<{ wk: string; text: string }> = []
    const alert = createFailureAlert({
      log: (m) => logged.push(m),
      deliver: (wk, text) => delivered.push({ wk, text }),
      windowFor: () => 'w-abc',
    })

    alert.alert({ requirementId: 'REQ-1', title: '【实施链暂停】REQ-1', content: '失败原因：[workflow] 产出为空' })

    const text = delivered[0]!.text
    // 指令壳：指挥来源窗口 LLM 立即弹框，且选项固定三处置
    expect(text).toContain('ask_user_question')
    expect(text).toContain('重跑该卡')
    expect(text).toContain('退回上游重新描述需求')
    expect(text).toContain('取消该任务')
    // 告警事实仍随指令壳带上（题干素材：发生了什么/为什么停）
    expect(text).toContain('【实施链暂停】REQ-1')
    expect(text).toContain('产出为空')
    // 宿主日志只记原始正文（排障），不含指令段
    expect(logged[0]).toContain('【实施链暂停】REQ-1')
    expect(logged[0]).not.toContain('ask_user_question')
  })

  it('来源窗口未知 → 只写日志：不投递、不抛（告警不静默丢）', () => {
    const logged: string[] = []
    const delivered: string[] = []
    const alert = createFailureAlert({
      log: (m) => logged.push(m),
      deliver: (wk) => delivered.push(wk),
      windowFor: () => undefined,
    })

    expect(() => alert.alert({ requirementId: 'REQ-1', title: 'T', content: 'C' })).not.toThrow()
    expect(logged).toHaveLength(1)
    expect(delivered).toEqual([])
  })

  it('任一通道抛错都不抛出（不阻断暂停与留痕）', () => {
    const alert = createFailureAlert({
      log: () => { throw new Error('log boom') },
      deliver: () => { throw new Error('deliver boom') },
      windowFor: () => 'w-abc',
    })

    expect(() => alert.alert({ requirementId: 'REQ-1', title: 'T', content: 'C' })).not.toThrow()
  })
})

describe('不变量：本插件代码不发飞书（2026-09-21 用户裁定）', () => {
  it('src/ 可执行代码不含 feishu / 飞书 / 飞书 webhook', () => {
    const offenders: string[] = []
    for (const file of tsFiles(SRC)) {
      const code = codeOnly(readFileSync(file, 'utf8'))
      if (/feishu|飞书|open\.feishu\.cn/i.test(code)) offenders.push(file.replace(SRC, 'src'))
    }
    expect(offenders).toEqual([])
  })
})
