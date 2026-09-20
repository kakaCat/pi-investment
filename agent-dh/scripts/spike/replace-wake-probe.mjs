// t1 探针：surface replace 是否具备唤醒 driver 的能力（运行时实证）
// user/message 的 data 形状**逐字对齐** NodeIsolationAdapter.replace()
import { Session } from '@deepseek-ai/dsh-session'

const proto = Session.prototype
const methods = Object.getOwnPropertyNames(proto).filter((n) => n !== 'constructor').sort()
const wakeish = methods.filter((n) => /wake|inbox|send|followup|steer|inject/i.test(n))
console.log('[1] Session 公开方法:', methods.join(', '))
console.log('[2] 其中可能唤醒 driver 的 API:', JSON.stringify(wakeish))

const s = Session.create('probe-session-0001')
const sys = s.append('system/message', { message: { role: 'system', content: [{ type: 'text', text: '系统段' }] } }, { surfaceOp: 'append' })
const u1 = s.append('user/message', { id: 'm1', role: 'user', content: [{ type: 'text', text: '历史一' }], source: { kind: 'user' } }, { surfaceOp: 'append' })
const a1 = s.append('assistant/message', { message: { role: 'assistant', content: [{ type: 'text', text: '历史二' }] } }, { surfaceOp: 'append' })
console.log('[3] replace 前 surface nodes:', JSON.stringify(s.surface.nodes))

// 与 NodeIsolationAdapter.replace 同形
const rep = s.append(
  'user/message',
  { id: 'pmboard-node-input-1', role: 'user', content: [{ type: 'text', text: '节点输入包' }], source: { kind: 'plugin', plugin: 'probe', form: 'notice', summary: '节点边界输入包' } },
  { surfaceOp: { op: 'replace', startSeq: u1.seq, endSeq: a1.seq }, sourceEventSeqs: [u1.seq, a1.seq] },
)
console.log('[4] replace 事件 seq =', rep.seq, '| 系统段 seq =', sys.seq)
console.log('[5] replace 后 surface nodes:', JSON.stringify(s.surface.nodes))
const msgs = s.deriveMessages()
console.log('[6] 模型可见消息:', msgs.map((m) => m.role + ':' + String(m.content?.[0]?.text ?? '')).join(' | '))
console.log('[7] 替换后还看得见历史吗:', msgs.some((m) => String(m.content?.[0]?.text ?? '').includes('历史')))
console.log('[8] 全程唤醒调用:', wakeish.length === 0 ? '无（Session API 无唤醒原语）' : '有：' + wakeish.join(','))

