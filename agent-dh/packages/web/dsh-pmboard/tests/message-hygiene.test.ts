/**
 * 消息与数值卫生门禁（REQ-47939a 返工，用户验收意见："魔法数字比较多，可以抽象专门解决拼接和魔法数字问题吗"）。
 *
 * 三件事被**钉死**，而不是靠自觉：
 *  ① `src/domain/**` 的拼接式消息必须为 **0**（规则层是消息的归属地，且它最小、能一次做到）；
 *  ② 其余层的拼接数按**棘轮**约束：只许下降，不许上升（当前值冻结在下面的 BASELINE 里）；
 *  ③ 具名数值与用户可见文案**必须来自单点文件**——工具超时不得写裸数字；弹框选项/徽章文案
 *     不得在 labels.ts 之外再写一份（此前 host 与 client 各一份，会静默漂移）。
 *
 * 为什么这么设计：用户点到的两个问题（拼接、魔法数字）本质都是"同一信息在多处被重新表达"。
 * 抽象（fmt / LIMITS / labels）解决了表达问题，而**门禁解决"以后会不会又散回去"**——没有门禁的
 * 抽象会在下一次赶工时被绕过（本需求已多次见证"门禁失效而假绿"）。
 *
 * 判读口径：注释行（以 * 或 // 开头）不计——文档里出现反例是好事，不该被判违规。
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const SRC = fileURLToPath(new URL('../src', import.meta.url))

function listTs(dir: string): string[] {
  if (!existsSync(dir)) return []
  const out: string[] = []
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name)
    if (e.isDirectory()) out.push(...listTs(p))
    else if (e.name.endsWith('.ts')) out.push(p)
  }
  return out
}
const rel = (p: string) => p.slice(SRC.length + 1).replace(/\\/g, '/')

/** 拼接式消息：中文字面量 + 连接（排除注释行）。 */
function concatSites(file: string): number {
  const text = readFileSync(file, 'utf8')
  let n = 0
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (t.startsWith('*') || t.startsWith('//') || t.startsWith('/*')) continue
    if (/'[^']*[\u4e00-\u9fff][^']*'\s*\+|\+\s*'[^']*[\u4e00-\u9fff]/.test(line)) n++
  }
  return n
}

const allTs = listTs(SRC)

/** 棘轮基线（2026-09-17 实测；只允许下降）。 */
const BASELINE: Record<string, number> = {
  application: 140, adapters: 5, tools: 47, http: 21, client: 98, shared: 11,
}

describe('消息卫生：拼接式消息', () => {
  it('规则层 src/domain/** 必须为 0（fmt 抽象已覆盖）', () => {
    const bad = allTs.filter(p => rel(p).startsWith('domain/') && !rel(p).endsWith('text/fmt.ts') && concatSites(p) > 0)
      .map(p => rel(p) + '（' + concatSites(p) + ' 处）')
    expect(bad, 'domain 仍有拼接式消息，请改用 fmt：\n' + bad.join('\n')).toEqual([])
  })

  it('其余层按棘轮约束：不得超过基线，且整体只降不升', () => {
    const now: Record<string, number> = {}
    for (const p of allTs) {
      const layer = rel(p).split('/')[0]!
      if (layer === 'domain') continue
      now[layer] = (now[layer] ?? 0) + concatSites(p)
    }
    const grown: string[] = []
    for (const [layer, base] of Object.entries(BASELINE)) {
      const cur = now[layer] ?? 0
      if (cur > base) grown.push(layer + '：' + base + ' → ' + cur + '（上升了，请先抽 fmt 再加消息）')
    }
    expect(grown, '拼接式消息增多：\n' + grown.join('\n')).toEqual([])
  })
})

describe('数值卫生：具名上限', () => {
  it('工具定义的 timeoutMs 不得写裸数字（须取自 LIMITS）', () => {
    const bad: string[] = []
    for (const p of allTs.filter(x => rel(x).startsWith('tools/'))) {
      for (const line of readFileSync(p, 'utf8').split('\n')) {
        if (/timeoutMs:\s*[0-9_]+/.test(line)) bad.push(rel(p) + '：' + line.trim())
      }
    }
    expect(bad, '工具超时请改用 domain/limits.ts 的具名常量：\n' + bad.join('\n')).toEqual([])
  })

  it('验收单批次缺省/上限不得写裸数字（须取自 LIMITS）', () => {
    const p = join(SRC, 'application/use-cases/AcceptSheet.ts')
    const text = readFileSync(p, 'utf8')
    expect(/\?\?\s*5\b|\.slice\(0,\s*10\)/.test(text), 'AcceptSheet 批次仍在写裸数字，请用 LIMITS.sheetBatchDefault/Max').toBe(false)
  })
})

describe('文案卫生：用户可见选项/徽章单点', () => {
  it('弹框选项与徽章文案只允许定义在 domain/text/labels.ts', () => {
    const LITERALS = ['✅ 通过', '🛠 改进（需修改）', '❓ 其他', '✅ 验收通过并归档', '⬜ 待验', '❌ 不通过']
    const bad: string[] = []
    for (const p of allTs) {
      if (rel(p) === 'domain/text/labels.ts') continue
      const text = readFileSync(p, 'utf8')
      for (const lit of LITERALS) {
        if (text.includes("'" + lit + "'")) bad.push(rel(p) + '：' + lit)
      }
    }
    expect(bad, '这些文案必须引用 domain/text/labels.ts（host 与 client 各写一份会静默漂移）：\n' + bad.join('\n')).toEqual([])
  })
})
