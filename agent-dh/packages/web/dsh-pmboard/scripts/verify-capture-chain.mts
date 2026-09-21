// REQ-f6307c T3 集成验证：真实代码 + 真实 ledger，模拟 unbound 窗口全链路
import { createSessionEventCaptureHook } from '../src/adapters/CaptureHook.js'
import { captureSectionText } from '../src/application/internal/capture-section.js'
import { shouldCaptureWindow } from '../src/application/internal/window.js'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'

const LEDGER = '/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json'
const store = new JsonLedgerRepository({ file: LEDGER })
await store.load()
const ledger = store.snapshot()

const testKey = 'session-verify-f6307c-0000-0000-0000-000000000000'
console.log('=== 步骤0：前提判定 ===')
console.log('shouldCaptureWindow(unbound test key):', shouldCaptureWindow(ledger, testKey))

const pending = new Map<string, { windowKey: string; text: string; capturedAt: number }>()
const handler = createSessionEventCaptureHook({
  snapshot: () => ledger,
  pending,
  now: () => Date.now(),
  logger: { info: () => {}, debug: () => {} },
})

console.log('\\n=== 步骤1：handler 处理 user/message（节点2→3）===')
handler(
  { id: testKey },
  { type: 'user/message', data: { content: '修复股票池刷新逻辑的 bug', source: { kind: 'user' } } },
)
console.log('pendingCapture.size:', pending.size)
console.log('pending text:', pending.get(testKey)?.text)

console.log('\\n=== 步骤2：captureSectionText（节点5，命中 pending → DYNAMIC）===')
const dynamicText = captureSectionText(ledger, { agent: { id: testKey } }, pending.get(testKey))
console.log('DYNAMIC text.length:', dynamicText.length)
console.log('--- 前 400 字 ---')
console.log(dynamicText.slice(0, 400))

console.log('\\n=== 步骤3：无 pending 时（节点5 → STATIC GUIDANCE）===')
const staticText = captureSectionText(ledger, { agent: { id: testKey } }, undefined)
console.log('STATIC text.length:', staticText.length)

console.log('\\n=== 步骤4：bound 窗口（本窗口）→ 空串 ===')
const boundKey = 'session-49bdb1dd-08e1-4ac1-a28a-daf1db28f99a'
const boundText = captureSectionText(ledger, { agent: { id: boundKey } }, { windowKey: boundKey, text: '修复 XX', capturedAt: Date.now() })
console.log('BOUND text.length:', boundText.length, '(预期 0)')

console.log('\\n=== 判定 ===')
const pass = pending.size === 1 && dynamicText.length > 0 && boundText.length === 0
console.log(pass ? '✅ PASS：unbound 全链路通畅（NODE-2→3→5 DYNAMIC），bound 正确零噪音' : '❌ FAIL')
process.exit(pass ? 0 : 1)

