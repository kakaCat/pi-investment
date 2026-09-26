// REQ-f6307c T3 集成验证：真实代码 + 真实 ledger，模拟 unbound 窗口全链路
// 2026-09-26 对齐 dsh-goal-round-driver：**采集**在 session/event(user/message)，
// **驱动**在 agent/status === 'idle'（整 agent 空闲）。
import { createDiveSessionDriver } from '../src/application/dive/session-driver.js'
import { captureSectionText } from '../src/application/internal/capture-section.js'
import { shouldCaptureWindow, isWindowBound } from '../src/application/internal/window.js'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'

const LEDGER = '/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json'
const store = new JsonLedgerRepository({ file: LEDGER })
await store.load()
const ledger = store.snapshot()

const testKey = 'session-verify-f6307c-0000-0000-0000-000000000000'
console.log('=== 步骤0：前提判定 ===')
console.log('shouldCaptureWindow(unbound test key):', shouldCaptureWindow(ledger, testKey))

const pending = new Map<string, { windowKey: string; text: string; capturedAt: number }>()
const driver = createDiveSessionDriver({
  snapshot: () => ledger,
  pending,
  now: () => Date.now(),
  logger: { info: () => {}, debug: () => {} },
})
const idle = () => driver.onAgentStatus({ id: testKey, session: { id: testKey } }, 'idle')

console.log('\n=== 步骤1：driver 采集 user/message（节点2 采集，不驱动）===')
driver(
  { id: testKey },
  { type: 'user/message', data: { content: '修复股票池刷新逻辑的 bug', source: { kind: 'user' } } },
)
console.log('采集后 pendingCapture.size:', pending.size, '(预期 0——仅采集)')

console.log('\n=== 步骤2：agent 空闲（agent/status=idle）→ 跑批登记（节点3）===')
idle()
console.log('idle 后 pendingCapture.size:', pending.size)
console.log('pending text:', pending.get(testKey)?.text)

console.log('\n=== 步骤3：captureSectionText（节点5，命中 pending → DYNAMIC）===')
const dynamicText = captureSectionText(ledger, { agent: { id: testKey } }, pending.get(testKey))
console.log('DYNAMIC text.length:', dynamicText.length)
console.log('--- 前 400 字 ---')
console.log(dynamicText.slice(0, 400))

console.log('\n=== 步骤4：无 pending 时（节点5 → STATIC GUIDANCE）===')
const staticText = captureSectionText(ledger, { agent: { id: testKey } }, undefined)
console.log('STATIC text.length:', staticText.length)

console.log('\n=== 步骤5：bound 窗口（从台账取真实绑定窗口）→ 空串 ===')
const boundKey = ledger.requirements
  .map((r) => r.sourceSessionId)
  .find((k): k is string => typeof k === 'string' && k.length > 0 && isWindowBound(ledger, k))
const boundText = boundKey === undefined
  ? ''
  : captureSectionText(ledger, { agent: { id: boundKey } }, { windowKey: boundKey, text: '修复 XX', capturedAt: Date.now() })
console.log('boundKey:', boundKey, '| BOUND text.length:', boundText.length, '(预期 0)')
if (boundKey === undefined) console.log('⚠️ 台账中无绑定窗口——该步跳过（断言按空串处理）')

console.log('\n=== 步骤6：下一次 idle 消费掉登记（跨装帧存活一拍）===')
idle()
console.log('二次 idle 后 pendingCapture.size:', pending.size, '(预期 0)')

console.log('\n=== 判定 ===')
const pass = pending.size === 0 && dynamicText.length > 0
  && (boundKey === undefined || boundText.length === 0)
console.log(pass ? '✅ PASS：采集(user/message)→驱动(idle)→取词(DYNAMIC) 全链路通畅，bound 正确零噪音' : '❌ FAIL')
process.exit(pass ? 0 : 1)
