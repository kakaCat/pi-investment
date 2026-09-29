
import { readFileSync } from 'node:fs'
import { buildGantt, renderTaskTable, buildTasksPage } from './src/client/views/timeline.js'
import { buildTaskColumns, buildTaskTable as stTable } from './src/client/views/stage-detail.js'
import { buildDagCanvas } from './src/client/views/dag-view.js'

const st = JSON.parse(readFileSync('/tmp/state.json', 'utf8')).data
const target = 'REQ-260927121324-abde'
const req = st.requirements.find((r: any) => r.id === target)
const ts = st.tasks.filter((t: any) => t.requirementId === target)
const childIds = ts.filter((t: any) => t.parentId).map((t: any) => t.id)
const now = Date.now()
const chk = (label: string, fn: () => string) => {
  try {
    const html = fn()
    const hits = childIds.filter((id: string) => html.includes(id))
    console.log(label.padEnd(28), '子卡 id 命中', (hits.length + '/' + childIds.length).padEnd(9), hits.slice(0, 3).join(' '))
  } catch (e: any) { console.log(label.padEnd(28), 'ERR', String(e.message).slice(0, 60)) }
}
console.log('目标需求', target, '| 全量卡', ts.length, '| 子卡', childIds.length)
chk('DAG 画布骨架', () => buildDagCanvas(ts))
chk('任务列 buildTaskColumns', () => buildTaskColumns(ts))
chk('stage 任务表', () => stTable(ts))
chk('甘特图 buildGantt', () => buildGantt(req, ts, now))
chk('任务表 renderTaskTable', () => renderTaskTable(ts, now))
chk('任务页 buildTasksPage', () => buildTasksPage(st, now))
