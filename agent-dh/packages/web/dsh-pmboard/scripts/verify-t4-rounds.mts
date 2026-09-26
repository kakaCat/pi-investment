// REQ-f6307c T4 连续测试：3 窗口 × 3 消息，验证 100% 首调提示注入
// 2026-09-26 对齐 dsh-goal-round-driver：采集走 user/message，驱动走 agent/status=idle。
import { createDiveSessionDriver } from '../src/application/dive/session-driver.js'
import { captureSectionText } from '../src/application/internal/capture-section.js'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'

const LEDGER = '/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json'
const store = new JsonLedgerRepository({ file: LEDGER })
await store.load()
const ledger = store.snapshot()

const cases = [
  { key: 'session-t4-round1-0000-0000-0000-000000000001', msg: '修复需求看板状态推进的 bug' },
  { key: 'session-t4-round2-0000-0000-0000-000000000002', msg: '新增需求看板批量导出功能' },
  { key: 'session-t4-round3-0000-0000-0000-000000000003', msg: '实现任务卡Markdown渲染优化' },
]

let pass = 0
for (const c of cases) {
  const pending = new Map<string, { windowKey: string; text: string; capturedAt: number }>()
  const driver = createDiveSessionDriver({
    snapshot: () => ledger,
    pending,
    now: () => Date.now(),
    logger: { info: () => {}, debug: () => {} },
  })
  const idle = () => driver.onAgentStatus({ id: c.key, session: { id: c.key } }, 'idle')
  // 模拟真实事件流：user/message（采集）→ Agent 回合结束转 idle（驱动）→ 下一回合组装 systemPrompt
  driver({ id: c.key }, { type: 'user/message', data: { content: c.msg, source: { kind: 'user' } } })
  idle()
  const text = captureSectionText(ledger, { agent: { id: c.key } }, pending.get(c.key))
  const mustFirstCall = text.includes('reqboard_capture') && text.includes('第一个工具调用')
  const ok = pending.size === 1 && text.length > 0 && mustFirstCall
  if (ok) pass++
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + c.key.slice(0, 22) + ' | pending=' + pending.size + ' | prompt=' + text.length + '字 | 含首调强制=' + mustFirstCall)
  // 下一拍 idle 消费登记（无新人类消息 → 不复登记）
  idle()
  const cleared = pending.size === 0
  console.log('     下一拍 idle 后 pending 清除: ' + (cleared ? 'OK' : 'LEAK!'))
  if (!cleared) pass--
}
console.log('')
console.log('连续测试: ' + pass + '/3 ' + (pass === 3 ? '100% PASS' : 'NOT-100%'))
process.exit(pass === 3 ? 0 : 1)
