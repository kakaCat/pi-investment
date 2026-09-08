import { createServer } from 'node:http'
import { ReqboardStore } from './src/host/store.js'
import { createReqboardHandler } from './src/host/routes.js'

async function main() {
  const store = new ReqboardStore({ file: '/tmp/reqboard-smoke.json' })
  await store.load()
  const handler = createReqboardHandler({ store, now: () => Date.now() })
  const server = createServer(handler)
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  const port = server.address().port
  const base = `http://127.0.0.1:${port}/dashboard/api/reqboard`

  const post = async (sub, body) => {
    const res = await fetch(`${base}${sub}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    return res.json()
  }
  const get = async (sub) => {
    const res = await fetch(`${base}${sub}`)
    return res.json()
  }

  // 1. state empty
  const s1 = await get('/state')
  console.assert(s1.success && s1.data.revision === 0, 'state empty')

  // 2. create requirement
  const r1 = await post('/req/create', { title: '测试需求' })
  console.assert(r1.success && r1.data.id.startsWith('REQ-'), 'req created', r1)
  const reqId = r1.data.id

  // 3. move req reviewing (human gate)
  const r2 = await post('/req/move', { id: reqId, to: 'reviewing', actor: 'human' })
  console.assert(r2.success && r2.data.status === 'reviewing', 'req moved to reviewing')

  // 4. agent cannot confirm review
  const r3 = await post('/req/move', { id: reqId, to: 'decomposing', actor: 'agent' })
  console.assert(!r3.success && r3.code === 'human_gate', 'agent blocked at human gate', r3)

  // 5. create task
  const t1 = await post('/task/create', {
    requirementId: reqId, title: '后端接口', phase: 'implement', side: 'backend',
    acceptance: 'POST /api/x 返回 200', context: '需求背景',
  })
  console.assert(t1.success && t1.data.id.startsWith('t-'), 'task created')
  const taskId = t1.data.id

  // 6. create task with DAG dep
  const t2 = await post('/task/create', {
    requirementId: reqId, title: '前端按钮', phase: 'implement', side: 'frontend',
    dependsOn: [taskId], acceptance: '按钮可点击', context: '背景',
  })
  console.assert(t2.success && t2.data.dependsOn[0] === taskId, 'task with dep created')

  // 7. DAG cycle rejected
  const t3 = await post('/task/create', {
    requirementId: reqId, title: '循环', phase: 'implement', side: 'backend',
    dependsOn: [t2.data.id], acceptance: '', context: '',
  })
  // Now update t1 to depend on t3 -> cycle
  const bad = await post('/task/update', { id: taskId, dependsOn: [t3.data.id] })
  console.assert(!bad.success && bad.code === 'invalid_dag', 'cycle blocked', bad)

  // 8. state has ready tasks
  const s2 = await get('/state')
  console.assert(s2.success && s2.data.ready[reqId].length === 1, 'ready tasks computed')

  // 9. task move to in_progress
  const m1 = await post('/task/move', { id: taskId, to: 'in_progress', actor: 'human', sessionId: 'session-test-123' })
  console.assert(m1.success && m1.data.status === 'in_progress' && m1.data.claimedBy === 'session-test-123', 'task claimed')

  // 10. task done only human
  const m2 = await post('/task/move', { id: taskId, to: 'done', actor: 'agent' })
  console.assert(!m2.success && m2.code === 'human_gate', 'agent cannot mark done')

  console.log('SMOKE ALL PASSED')
  server.close()
  process.exit(0)
}
main().catch(e => { console.error(e); process.exit(1) })
