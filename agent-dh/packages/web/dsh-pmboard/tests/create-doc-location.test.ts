// serves: FR-7
/**
 * reqboard_create 文档位置回归（REQ-260924213231-b1c4 T-10 / FR-7 / UC-4 / TC-11~TC-13）。
 *
 * 背景：立项降级路径（弹框通道不可用，用户在对话里给出名称/类型/难度）此前会丢第四问——
 * reqboard_create 没有 doc_location 入参，台账 docBasePath 恒 undefined，文档位置只能靠
 * 消费端缺省兜底且无从留痕。本测试锁定三条正向事实与一条故障注入：
 *   TC-11 不传 doc_location → 返回 doc_location='docs/requirements/<REQ>/'、defaults_used
 *         含 doc_location，且台账 docBasePath 同值（回落落在台账，不只留在返回体）；
 *   TC-12 传 docs/rfcs/ → 台账 docBasePath='docs/rfcs/'，产物路径按它生成；
 *   TC-13 返回 status 与台账一致（不撒谎）；
 *   异常流 绝对路径 / 含 .. → REQBOARD_INVALID_INPUT，且不写台账（不静默改路径）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { SystemClock } from '../src/adapters/SystemClock.js'
import { RandomIdFactory } from '../src/adapters/RandomIdFactory.js'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { UserQuestionsAdapter } from '../src/adapters/UserQuestionsAdapter.js'
import { defineCreateTool } from '../src/tools/index.js'
import { requirementDocPath } from '../src/application/internal/node-input-package.js'
import { CAPTURE_DEFAULTS, CAPTURE_QUESTION_IDS } from '../src/application/internal/capture-mapping.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-doc-location-1'

let root: string
let store: JsonLedgerRepository

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-doc-loc-'))
  store = new JsonLedgerRepository({ file: join(root, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

/** 真适配器构造 UseCaseDeps（工具壳吃 application 端口）；无 agents/sessionProjections → 认证降级放行。 */
const deps = (): any => ({
  repo: store,
  docs: new FileDocRepository({ workspaceRoot: root }),
  clock: new SystemClock(),
  ids: new RandomIdFactory(),
  session: new SessionProbeAdapter({}),
  questions: new UserQuestionsAdapter(() => undefined),
  doneThrottleMs: 0,
})

const ARGS = { title: '降级路径立项', category: 'feature' }

/** 每次调用新建工具（与真实装配一致），execute 走完整 shell → 用例 → 台账链路。 */
const run = (args: Record<string, unknown>) =>
  (defineCreateTool(deps()) as any).execute(args, { agent: { id: W } })

const ledgerReq = (id: string): RequirementRecord =>
  store.snapshot().requirements.find(r => r.id === id)!

describe('reqboard_create · 文档位置（FR-7 降级路径补第四问）', () => {
  it('TC-11 不传 doc_location → 显式回落默认值 + defaults_used 留痕，台账 docBasePath 同值', async () => {
    const out = await run({ ...ARGS })
    expect(out.success).toBe(true)
    expect(out.doc_location).toBe(CAPTURE_DEFAULTS.docLocation)
    expect(out.defaults_used).toEqual([CAPTURE_QUESTION_IDS.doc_location])
    expect(out.note).toContain('回落')

    const req = ledgerReq(out.requirement_id)
    expect(req.docBasePath).toBe(CAPTURE_DEFAULTS.docLocation)
    // 产物路径与回落值同源（消费端 requirementDocPath 解析一致）。
    expect(requirementDocPath(req)).toBe('docs/requirements/' + req.id + '/requirement.md')
  })

  it('TC-12 传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成', async () => {
    const out = await run({ ...ARGS, doc_location: 'docs/rfcs/' })
    expect(out.doc_location).toBe('docs/rfcs/')
    expect(out.defaults_used).toEqual([])

    const req = ledgerReq(out.requirement_id)
    expect(req.docBasePath).toBe('docs/rfcs/')
    expect(requirementDocPath(req)).toBe('docs/rfcs/' + req.id + '/requirement.md')
  })

  it('TC-13 返回 status 与台账一致（当前落点 draft，不谎报推进）', async () => {
    const out = await run({ ...ARGS })
    const req = ledgerReq(out.requirement_id)
    expect(out.status).toBe(req.status)
    expect(store.snapshot().requirements).toHaveLength(1)
  })

  it('异常流：绝对路径 / 含 .. 的路径 → REQBOARD_INVALID_INPUT，且不写台账（不静默改路径）', async () => {
    for (const bad of ['/etc/passwd', '../escape', 'docs/../../escape', 'C:\\Windows']) {
      await expect(run({ ...ARGS, doc_location: bad })).rejects.toMatchObject({ code: 'REQBOARD_INVALID_INPUT' })
    }
    expect(store.snapshot().requirements).toHaveLength(0)
  })

  it('schema：doc_location 入参 + doc_location/defaults_used 返回键已声明（DSH 绑定层不拒收）', () => {
    const tool = defineCreateTool(deps()) as any
    const params = tool?.parameters?.properties ?? {}
    expect(params.doc_location?.type).toBe('string')
    const props = tool?.output?.schema?.properties ?? tool?.schema?.output?.schema?.properties ?? {}
    expect(props.doc_location?.type).toBe('string')
    expect(props.defaults_used?.type).toBe('array')
  })
})
