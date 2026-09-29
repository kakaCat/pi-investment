/**
 * 卡片层契约测试（2026-09-28）——laneOf / chainMissing / collapseToCardLevel + 泳道渲染口径。
 *
 * 对应本窗口诊断的三类缺陷：
 *   D1 泳道「联调中/测试中/待复核」结构性为空（列按 status 过滤，而父卡中段状态不可达）；
 *   D2 DAG 混两个抽象层（子卡与父卡同为节点）；
 *   D4 「不需子卡」与「需要但未生成」不可分（stages: [] = solo 声明）。
 */
import { describe, it, expect } from 'vitest'
import { laneOf, chainMissing, collapseToCardLevel } from '../src/client/dag/progress-bar.js'
import { renderNodePanel } from '../src/client/node-panel.js'
import { ALL_STAGE_KEYS } from '../src/shared/protocol.js'

const kid = (stageKind: string, status: string) => ({ id: 'k-' + stageKind, stageKind, status, title: stageKind })

describe('laneOf：泳道列 = 卡所处环节', () => {
  it('非 in_progress 用卡自身状态', () => {
    expect(laneOf({ status: 'todo' }, [])).toBe('todo')
    expect(laneOf({ status: 'done' }, [kid('test', 'done')])).toBe('done')
  })
  it('无子卡（solo / 存量卡）用自身状态——存量卡五段仍可显示', () => {
    expect(laneOf({ status: 'in_progress' }, [])).toBe('in_progress')
    expect(laneOf({ status: 'integrating' }, [])).toBe('integrating')
    expect(laneOf({ status: 'testing' }, [])).toBe('testing')
  })
  it('有链的父卡按链上第一个未完成子卡的阶段归位（中段列不再为空）', () => {
    expect(laneOf({ status: 'in_progress' }, [kid('dev', 'in_progress')])).toBe('in_progress')
    expect(laneOf({ status: 'in_progress' }, [kid('dev', 'done'), kid('integrate', 'in_progress')])).toBe('integrating')
    expect(laneOf({ status: 'in_progress' }, [kid('dev', 'done'), kid('integrate', 'done'), kid('review', 'in_progress')])).toBe('in_review')
    expect(laneOf({ status: 'in_progress' }, [kid('dev', 'done'), kid('integrate', 'done'), kid('review', 'done'), kid('test', 'in_progress')])).toBe('testing')
  })
  it('链全绿而父卡未收尾 → 待复核（把卡住的卡浮出来）', () => {
    expect(laneOf({ status: 'in_progress' }, [kid('dev', 'done'), kid('test', 'done')])).toBe('in_review')
  })
  it('未知 stageKind 回落开发中；链序按 STAGE_ORDER 而非数组顺序', () => {
    expect(laneOf({ status: 'in_progress' }, [kid('fix', 'in_progress')])).toBe('in_progress')
    expect(laneOf({ status: 'in_progress' }, [kid('test', 'todo'), kid('dev', 'in_progress')])).toBe('in_progress')
  })
})

describe('chainMissing：链未生成 vs 显式 solo', () => {
  it('in_progress + 无子卡 + 未声明无链 → 缺链', () => {
    expect(chainMissing({ status: 'in_progress' }, [])).toBe(true)
    expect(chainMissing({ status: 'in_progress', stages: ['dev', 'review'] }, [])).toBe(true)
  })
  it('显式 stages: []（solo）→ 不缺链（这就是「不需子卡」）', () => {
    expect(chainMissing({ status: 'in_progress', stages: [] }, [])).toBe(false)
  })
  it('todo（未开工，懒展开是正常态）/ 有子卡 → 不缺链', () => {
    expect(chainMissing({ status: 'todo' }, [])).toBe(false)
    expect(chainMissing({ status: 'in_progress' }, [kid('dev', 'todo')])).toBe(false)
  })
})

describe('collapseToCardLevel：DAG 折叠到卡片层', () => {
  const tasks = [
    { id: 'p1', dependsOn: [] },
    { id: 'p2', dependsOn: ['p1'] },
    { id: 'p3', dependsOn: ['k1'] },
    { id: 'p4', dependsOn: ['zzz'] },
    { id: 'k1', parentId: 'p1', dependsOn: ['p2'], stageKind: 'dev' },
    { id: 'k2', parentId: 'p1', dependsOn: ['k1'], stageKind: 'integrate' },
    { id: 'k3', parentId: 'p1', dependsOn: ['p2', 'k2'], stageKind: 'review' },
  ]
  it('节点集 = 顶层卡；子卡不出现为节点', () => {
    const { tops } = collapseToCardLevel(tasks)
    expect(tops.map((t) => t.id)).toEqual(['p1', 'p2', 'p3', 'p4'])
  })
  it('指向子卡的依赖上提到父卡；同一父卡内部链边丢自环；跨卡依赖保留', () => {
    const { deps } = collapseToCardLevel(tasks)
    expect(deps['p1']).toEqual(['p2'])
    expect(deps['p2']).toEqual(['p1'])
    expect(deps['p3']).toEqual(['p1'])
  })
  it('悬空依赖（指向队列外）被丢弃——画不出节点的边是噪声', () => {
    const { deps } = collapseToCardLevel(tasks)
    expect(deps['p4']).toEqual([])
  })
})

// ── 渲染层：泳道中段列真的会有卡（D1 的回归钉） ─────────────────────────────
function makeTask(over: Record<string, unknown> = {}) {
  return { id: 't-aaa001', title: '任务一', status: 'todo', phase: 'implement', side: 'backend', dependsOn: [], acceptance: '', executions: [], ...over }
}
function makeOverview(tasks: unknown[]) {
  const bodies: Record<string, unknown> = {
    draft: {}, brainstorming: {}, design: {},
    decomposing: { decompositionDoc: undefined, tasks: [], planTasks: [] },
    implementing: { tasks, byWindow: {} },
    accepting: {}, archived: {},
  }
  return {
    requirementId: 'REQ-test', category: 'feature', currentStage: 'implementing',
    stages: ALL_STAGE_KEYS.map((stage) => ({
      stage, enabled: true, artifacts: [], pendingConfirmation: false,
      timeline: [{ status: stage, at: Date.now(), by: { kind: 'human' } }],
      body: bodies[stage],
    })),
  }
}
const REQ = { id: 'REQ-test', title: '卡片层测试', category: 'feature' }
/** 截取某一列的 HTML（从 data-col 到下一列）。 */
function col(html: string, key: string): string {
  const start = html.indexOf('data-col="' + key + '"')
  if (start < 0) return ''
  const rest = html.slice(start)
  const next = rest.indexOf('data-col="', 10)
  return next < 0 ? rest : rest.slice(0, next)
}

describe('泳道渲染：联调中/测试中列不再结构性为空（D1）', () => {
  it('integrate 子卡在跑的父卡落在「联调中」列，且不在「开发中」列', () => {
    const html = renderNodePanel({
      overview: makeOverview([
        makeTask({ id: 't-p1', title: '父卡一', status: 'in_progress' }),
        makeTask({ id: 't-k1', title: '父卡一·研发', status: 'done', parentId: 't-p1', stageKind: 'dev' }),
        makeTask({ id: 't-k2', title: '父卡一·联调', status: 'in_progress', parentId: 't-p1', stageKind: 'integrate' }),
      ]),
      stage: 'implementing', requirement: REQ,
    } as never)
    expect(col(html, 'integrating')).toContain('t-p1')
    expect(col(html, 'integrating')).not.toContain('card-chain') // 2026-09-29 裁定 E：不再展示链进度
    expect(col(html, 'in_progress')).not.toContain('t-p1')
  })
  it('缺链的 chain 卡打「链未生成」标；显式 solo（stages: []）不打标', () => {
    const missing = renderNodePanel({
      overview: makeOverview([makeTask({ id: 't-m1', title: '缺链卡', status: 'in_progress' })]),
      stage: 'implementing', requirement: REQ,
    } as never)
    expect(missing).toContain('链未生成')
    const solo = renderNodePanel({
      overview: makeOverview([makeTask({ id: 't-s1', title: '单卡', status: 'in_progress', stages: [] })]),
      stage: 'implementing', requirement: REQ,
    } as never)
    expect(solo).not.toContain('链未生成')
  })
})
