/**
 * reqboard 工具 schema 冒烟（REQ-260927144541-0481 FR-7）。
 *
 * 三件事：
 *  ① 构造**全部**已注册工具（此前只构造 4 个——其余工具的 schema 违规要等插件装配才炸）；
 *  ② 参数 DSL 形状：声明段必须是 { 字段名: DSL }，不得出现 `parameters: { schema: … }`（design I-6②）；
 *  ③ 工厂清单齐备（少一个即红——防退化为"只覆盖部分还自称全量"）。
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import * as toolModules from '../src/tools/index.js'

// defineTool 编译 schema 不触碰 deps 执行路径；构造用最小 stub 即可
const deps = {} as never

/** 全部注册工具工厂（与 src/index.ts 的注册清单同源；新增工具必须加进来）。 */
const FACTORIES = [
  'defineCreateTool',
  'defineCaptureTool',
  'defineStatusTool',
  'defineTaskReportTool',
  'defineDecomposeTool',
  'defineSubmitTool',
  'defineAskConfirmTool',
  'defineConfirmReceiptTool',
  'defineAcceptSheetTool',
  'defineTaskExecuteTool',
  'defineAdvanceTool',
  'defineRunStatusTool',
  'defineTaskStatusTool',
  'defineNoteInterruptionTool',
  'defineClearPauseTool',
  'defineMoveTool',
  'defineTaskMoveTool',
  'defineTaskTreeTool',
] as const

const factoryOf = (name: string): ((d: unknown) => any) | undefined =>
  (toolModules as unknown as Record<string, (d: unknown) => any>)[name]

describe('reqboard 工具 schema（构造即编译全部工具）', () => {
  it('工厂清单齐备（18 个全量；少一个即红）', () => {
    expect(FACTORIES).toHaveLength(18)
    for (const name of FACTORIES) expect(typeof factoryOf(name), name + ' 未导出').toBe('function')
  })

  for (const name of FACTORIES) {
    it(name + '：schema 合法（构造不抛）', () => {
      expect(() => factoryOf(name)!(deps)).not.toThrow()
    })
  }
})

/** 递归列出目录下全部 .ts（与 output-contract 同款扫描口径）。 */
function readdirSyncSafe(dir: string): string[] {
  const fs = require('node:fs') as typeof import('node:fs')
  const out: string[] = []
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = dir + '/' + e.name
    if (e.isDirectory()) out.push(...readdirSyncSafe(p))
    else if (e.name.endsWith('.ts')) out.push(p)
  }
  return out
}

/**
 * 参数 DSL 形状（design I-6②）——**源码级**检查：声明段必须是 { 字段名: DSL }，不得出现
 * parameters: { schema: … }（旧式 JSON Schema 写法）。为什么不构造后看对象：defineTool 会把 DSL
 * 归一化成 { type:'object', properties:{…} }，构造后的形状已经看不出原来怎么写的了。
 *
 * 例外是**显式留债**：clear_pause 仍是旧式写法，其修复属需求级工具治理
 * （requirement P7 / design use-cases §范围外，另立项），不在本需求改其行为。
 */
const LEGACY_PARAM_SHAPE = new Set(['ClearPauseTool'])

describe('reqboard 工具参数 DSL 形状（源码级：不得出现 parameters.schema）', () => {
  const ROOT = fileURLToPath(new URL('../src/tools', import.meta.url))
  const files = readdirSyncSafe(ROOT).filter(f => !f.endsWith('prompt.ts') && !f.endsWith('index.ts'))

  it('扫描器自检：至少扫到 15 个工具源文件', () => {
    expect(files.length).toBeGreaterThanOrEqual(15)
  })

  for (const f of files) {
    const name = f.slice(f.lastIndexOf('/') + 1).replace(/\.ts$/, '')
    if (LEGACY_PARAM_SHAPE.has(name)) {
      it(name + '：旧式 parameters.schema（显式留债，另立项治理）', () => {
        expect(readFileSync(f, 'utf8')).toMatch(/parameters:\s*\{\s*schema\s*:/)
      })
      continue
    }
    it(name + '：parameters 是 { 字段名: DSL } 形状', () => {
      const src = readFileSync(f, 'utf8')
      expect(/parameters:\s*\{\s*schema\s*:/.test(src), name + ' 仍是旧式 parameters.schema').toBe(false)
    })
  }
})
