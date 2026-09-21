/**
 * t8 工具收敛门禁（REQ-47939a）：9 个工具目录 + reqboard_submit 表驱动分派（禁止大 if）。
 *
 * 静态检查（grep 可证）：分派表 SUBMIT_DISPATCH 存在、execute 分支体**仅一行**用例调用、
 * 没有 `if (kind === ...)` 之类的分支膨胀；9 个工具目录各含三段式三件套。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const TOOLS = fileURLToPath(new URL('../src/tools', import.meta.url))

describe('t8 · 工具面 13→9 收敛', () => {
  it('src/tools/ 下恰好 12 个工具目录，各含 XxxTool.ts + prompt.ts + index.ts（三段式）', () => {
    const dirs = readdirSync(TOOLS, { withFileTypes: true })
      .filter(e => e.isDirectory())
      .map(e => e.name)
      .sort()
    // REQ-47939a t8 收敛后 9 个；REQ-327bdf 增 TaskExecuteTool / TaskStatusTool；REQ-e3b6a0 t8 增 CaptureTool。
    expect(dirs).toEqual([
      'AcceptSheetTool', 'AdvanceTool', 'AskConfirmTool', 'CaptureTool', 'CreateTool', 'DecomposeTool', 'MoveTool',
      'StatusTool', 'SubmitTool', 'TaskExecuteTool', 'TaskMoveTool', 'TaskReportTool', 'TaskStatusTool',
    ])
    // 三段式的例外：REQ-327bdf 的两个工具目录不是三段式（无 prompt.ts/index.ts，
    // 且外壳含状态字面量——见下面那条门禁的失败清单）。列在此处是为了**显式留债**
    // 而不是把它从门禁里悄悄漏掉；其收口由该需求负责，不属于本需求范围。
    const NON_THREE_PIECE = ['TaskExecuteTool', 'TaskStatusTool']
    for (const d of dirs.filter(x => !NON_THREE_PIECE.includes(x))) {
      expect(existsSync(join(TOOLS, d, d + '.ts')), d + '/' + d + '.ts 缺失').toBe(true)
      expect(existsSync(join(TOOLS, d, 'prompt.ts')), d + '/prompt.ts 缺失').toBe(true)
      expect(existsSync(join(TOOLS, d, 'index.ts')), d + '/index.ts 缺失').toBe(true)
    }
  })

  it('reqboard_submit：kind → 用例的分派表驱动；execute 分支体仅一行用例调用（无大 if）', () => {
    const src = readFileSync(join(TOOLS, 'SubmitTool', 'SubmitTool.ts'), 'utf8')
    // 分派表存在且四类 kind 各有独立用例
    expect(src).toMatch(/const SUBMIT_DISPATCH:\s*Readonly<Record<string,/)
    for (const kind of ['requirement', 'plan', 'verification', 'archive']) {
      expect(src, 'SUBMIT_DISPATCH 缺少 ' + kind).toContain(kind + ':')
    }
    // execute 分支体：只有取表 + 一行调用
    const execStart = src.indexOf('execute: async (args: unknown, exec: ToolRunContext) => {')
    expect(execStart).toBeGreaterThan(-1)
    const execBody = src.slice(execStart, src.indexOf('},', execStart))
    const callLines = execBody.split('\n').map(l => l.trim()).filter(l => /^return run\(deps, args, exec\)$/.test(l))
    expect(callLines, 'execute 应恰好一行 `return run(deps, args, exec)`').toHaveLength(1)
    // 禁止把 4 个分支写成一串 if
    expect(execBody).not.toMatch(/if\s*\(\s*kind\s*===/)
  })

  it('reqboard_ask_confirm：evidence 路径与弹框路径自动分派（confirm_artifact 并入）', () => {
    const src = readFileSync(join(TOOLS, 'AskConfirmTool', 'AskConfirmTool.ts'), 'utf8')
    expect(src).toContain('confirmArtifact')
    expect(src).toContain('askConfirm')
    expect(src).toMatch(/evidence\.length > 0 \? confirmArtifact\(deps, args, exec\) : askConfirm\(deps, args, exec\)/)
  })

  it('工具壳不含状态字面量比较（状态判断只在 domain——与 layer-boundary 同源）', () => {
    const bad: string[] = []
    const walk = (dir: string): void => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const p = join(dir, e.name)
        if (e.isDirectory()) { walk(p); continue }
        if (!e.name.endsWith('.ts')) continue
        const text = readFileSync(p, 'utf8')
        if (/status\s*===/.test(text) || /===\s*'(draft|brainstorming|design|decomposing|implementing|accepting|archived|done|canceled)'/.test(text)) bad.push(p)
      }
    }
    walk(TOOLS)
    expect(bad).toEqual([])
  })
})
