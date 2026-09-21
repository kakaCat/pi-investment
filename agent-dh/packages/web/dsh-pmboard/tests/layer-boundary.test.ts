/**
 * 层边界机械检查（REQ-47939a t1）——把 design/architecture.md 的依赖方向表变成**可失败的检查**。
 *
 * 为什么先立这个测试再搬代码：REQ-2e9473 的教训是"只测成功路径等于没测"。分层重构最容易
 * 无声跑偏的方式不是编译错误，而是某天有人顺手在 domain 里 \`import { readFileSync }\` 或
 * 在上层又写一遍 \`status === 'design'\` —— 编译、测试、review 全都不报，规则却已经两处实现。
 * 本测试就是那条会响的线。
 *
 * 口径对齐：design/architecture.md §2 依赖方向表 / INV-2。
 * 防假绿：末尾两条自检断言（扫描器命中文件数下限、import 抽取自检）——扫描器自身失效时
 * 必须让测试红，而不是安静通过（2026-09-17 契约扫描器踩过这个坑）。
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import { REQBOARD_ERROR_CODES, domainError } from '../src/domain/errors.js'
import { REQ_TRANSITIONS } from '../src/domain/requirement/RequirementStatus.js'
import { TASK_TRANSITIONS } from '../src/domain/task/TaskStatus.js'

const SRC = fileURLToPath(new URL('../src', import.meta.url))

/** 递归列出 .ts 文件（SRC 下的绝对路径）。 */
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

/** 抽取 import 的模块说明符（静态 / 类型 / 动态 import / 副作用 import 全覆盖）。 */
function extractImports(text: string): string[] {
  const specs: string[] = []
  const re = /(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) specs.push(m[1]!)
  return specs
}

interface LayerRule { forbidden: RegExp[]; why: string }

const LAYER_RULES: Record<string, LayerRule> = {
  domain: {
    forbidden: [
      /^node:/, /^@deepseek-ai\//, /^@pi-investment\//,
      /^\.\.\/(application|adapters|tools|http|client|host|shared)\//,
    ],
    why: 'domain 是最内层：不许碰 I/O（node:）、框架（@deepseek-ai）、上层模块与 shared',
  },
  application: {
    forbidden: [
      /^node:/, /^@deepseek-ai\//, /^@pi-investment\//,
      /^\.\.\/(adapters|tools|http|client|host)\//,
    ],
    why: 'application 只依赖 domain 与 shared 的**类型**；一切 I/O 走端口',
  },
  shared: {
    forbidden: [/^node:/, /^\.\.\/(application|adapters|tools|http|client|host)\//],
    why: 'shared 是 host 与 client 共用的契约层，不得依赖任何一侧实现',
  },
}

const allTs = listTs(SRC)
const rel = (p: string) => p.slice(SRC.length + 1).replace(/\\/g, '/')

describe('层边界：依赖方向（architecture.md §2）', () => {
  it('扫描器自检：至少扫到 20 个 .ts 文件（防目录写错而静默通过）', () => {
    expect(allTs.length).toBeGreaterThanOrEqual(20)
  })

  it('扫描器自检：extractImports 能抽出说明符', () => {
    const sample = "import a from 'pkg-a'\nimport type { B } from '../shared/protocol.js'\nimport('dyn')\nimport './side.js'"
    expect(extractImports(sample)).toEqual(['pkg-a', '../shared/protocol.js', 'dyn', './side.js'])
  })

  for (const layer of Object.keys(LAYER_RULES)) {
    const rule = LAYER_RULES[layer]!
    it(layer + '/ 不得 import 禁止项（' + rule.why + '）', () => {
      const files = allTs.filter(p => rel(p).startsWith(layer + '/'))
      if (layer === 'domain' || layer === 'application') {
        expect(files.length, layer + '/ 下应有文件（骨架已立）').toBeGreaterThanOrEqual(1)
      }
      const bad: string[] = []
      for (const f of files) {
        for (const spec of extractImports(readFileSync(f, 'utf8'))) {
          if (rule.forbidden.some(re => re.test(spec))) bad.push(rel(f) + ' -> ' + spec)
        }
      }
      expect(bad, layer + '/ 出现越界 import：\n' + bad.join('\n')).toEqual([])
    })
  }

  it('domain/ 内不得使用 Date.now() / Math.random()（时间与 ID 一律注入，保证用例可复现）', () => {
    const bad: string[] = []
    for (const f of allTs.filter(p => rel(p).startsWith('domain/'))) {
      const text = readFileSync(f, 'utf8')
      if (/Date\.now\s*\(/.test(text)) bad.push(rel(f) + ' -> Date.now()')
      if (/Math\.random\s*\(/.test(text)) bad.push(rel(f) + ' -> Math.random()')
    }
    expect(bad, 'domain/ 出现非确定性来源：\n' + bad.join('\n')).toEqual([])
  })

  it('tools/ 与 http/ 内不得出现状态字面量（比较式与判定器实参都不行——状态判断只在 domain）', () => {
    // 2026-09-17 修洞：原实现只匹配 `===`，于是 `status !== 'accepting'` / `'pending'` 全部漏过，
    // 而实测 src/http/ 有 8 处这种 `!==` 比较 —— 门禁绿灯只是因为它没看。同一类事故（"门禁失效而假绿"）
    // 本轮已出现多次，故此处同时覆盖：① 任意比较算子 ② 判定器实参里的字面量。
    const NAMES = [
      ...Object.keys(REQ_TRANSITIONS), ...Object.keys(TASK_TRANSITIONS),
      'pending', 'passed', 'failed', // 验收单项状态（VerificationItem.status）
    ].join('|')
    // 三层口径，逐层收紧（每条都是实测踩出来的洞）：
    //  ① 比较式任意算子（原实现只查 ===，漏了 src/http/ 的 8 处 !==）
    //  ② 判定器实参（statusIs(x, 'accepting') 只是把运算符搬进 domain，规则仍在适配层）
    //  ③ **任何独立的状态名字面量**（countStatus(items,'passed') / isEveryStatus(...) 这类也漏）
    const CMP = new RegExp("status\\s*(?:[!=]==|[!=]=)\\s*'(" + NAMES + ")'")
    const ARG = new RegExp("\\bstatus(?:Is|In|NotEquals|Equals)\\s*\\([^)]*'(" + NAMES + ")'")
    const LIT = new RegExp("'(" + NAMES + ")'")
    const bad: string[] = []
    for (const layer of ['tools', 'http']) {
      for (const f of allTs.filter(p => rel(p).startsWith(layer + '/'))) {
        const text = readFileSync(f, 'utf8')
        if (CMP.test(text) || ARG.test(text) || LIT.test(text)) bad.push(rel(f))
      }
    }
    expect(bad, layer0Msg(bad)).toEqual([])
  })
})

function layer0Msg(bad: string[]): string {
  return bad.length === 0 ? '' : '适配层出现状态判断（应改为调用 domain 的判定函数）：\n' + bad.join('\n')
}

describe('t1 骨架产物存在且可用（本测试直接引用，防"文件在但没用上"）', () => {
  it('src/domain/errors.ts：错误码表 + domainError 构造器', () => {
    expect(existsSync(join(SRC, 'domain/errors.ts'))).toBe(true)
    expect(REQBOARD_ERROR_CODES.invalidTransition).toBe('invalid_transition')
    expect(REQBOARD_ERROR_CODES.humanGate).toBe('human_gate')
    expect(REQBOARD_ERROR_CODES.doneEvidenceMissing).toBe('done_evidence_missing')
    const err = domainError(REQBOARD_ERROR_CODES.bulkClose, 'x')
    expect((err as { code?: string }).code).toBe('bulk_close')
  })

  it('src/application/ports.ts：六个端口接口齐备', () => {
    const p = join(SRC, 'application/ports.ts')
    expect(existsSync(p)).toBe(true)
    const text = readFileSync(p, 'utf8')
    for (const name of ['ReqboardRepository', 'DocRepository', 'Clock', 'IdFactory', 'SessionProbe', 'UserQuestionPort']) {
      expect(text, '缺少端口 ' + name).toContain('export interface ' + name)
    }
  })
})
