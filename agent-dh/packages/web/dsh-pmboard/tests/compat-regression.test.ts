/**
 * 迁移与兼容核验 · 静态与反面断言（REQ-260928222643-4d34 · 父卡 t-316227 · serves: FR-4, FR-5）。
 *
 * 本需求**无数据迁移、无 schema 变更**：不新增台账字段、不动 REQBOARD_SCHEMA_VERSION。
 * 唯一内部调用方 `NodePanelInput` 已随实现卡同批收敛（面板侧不再传 injection/isolation）。
 * 本文件把「不误删、不回归、非粘滞」钉成可执行断言（C-1~C-6），与 tests/node-panel.test.ts 的
 * TC-5/TC-5′「一句话断言」互补——本卡覆盖 看板消费方 / api 导出面 / 函数本体 / 后端路由 / 调用方收敛 / 非粘滞 六个面。
 *
 *   C-1 反面断言：看板自己的注入留痕消费方保留（board-mount.ts 恰好 1 处 fetchInjectionInfo）
 *   C-2 反面断言：api.ts 两个留痕查询函数仍导出（看板消费方依赖，禁「按整目录 grep 一把删」）
 *   C-3 保留断言：node-panel-process.ts 的 renderProcessFold 函数本体保留（只断调用，不删函数）
 *   C-4 保留断言：后端两条只读路由（/injection-log、/isolation-log）仍在（分发 + 处理器）
 *   C-5 调用方收敛：src/ 内 NodePanelInput 仅渲染器使用，面板侧两文件零 injection/isolation 字样
 *   C-6 非粘滞：一次性交接模块不落浏览器存储 / 不进 URL / 不挂 window
 *
 * 注：`git diff` 变更面与 REQBOARD_SCHEMA_VERSION **版本值未变**的核对属父卡证据步骤（版本级、跨文件），
 * 不在本文件断言；此处只锁「常量仍导出且形状未变（整数）」。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { REQBOARD_SCHEMA_VERSION } from '../src/shared/protocol.js'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))
const read = (rel: string): string => readFileSync(join(SRC, rel), 'utf8')
const countOf = (hay: string, needle: string): number => hay.split(needle).length - 1

/** 递归收集 src/ 下全部 .ts（与 node-panel-process-map.test.ts 同款手写遍历，不引第三方 glob）。 */
function walkTs(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walkTs(p, acc)
    else if (name.endsWith('.ts')) acc.push(p)
  }
  return acc
}

describe('迁移与兼容核验 · 看板消费方与后端接口零回归（REQ-260928222643-4d34 t-316227）', () => {
  it('C-1 反面断言：board-mount.ts 的 fetchInjectionInfo 恰好 1 处（防整目录误删）', () => {
    const board = read('client/board-mount.ts')
    expect(countOf(board, 'fetchInjectionInfo')).toBe(1)
    // 且该处仍是真实调用（不是注释/死引用）
    expect(board).toContain('api.fetchInjectionInfo(')
  })

  it('C-2 反面断言：api.ts 两个留痕查询函数仍在导出面', () => {
    const api = read('client/api.ts')
    expect(api).toContain('export function fetchInjectionInfo(')
    expect(api).toContain('export function fetchIsolationLog(')
  })

  it('C-3 保留断言：node-panel-process.ts 的函数本体保留、但渲染器已断调用', () => {
    const proc = read('client/node-panel-process.ts')
    expect(proc).toContain('export function renderProcessFold(')
    expect(proc).toContain('export interface ProcessFoldContext')
    // 只断调用：渲染器不再引用（函数可留）
    expect(read('client/node-panel.ts')).not.toContain('renderProcessFold')
  })

  it('C-4 保留断言：后端两条只读路由仍在（分发 + 处理器导出）', () => {
    const routes = read('http/routes.ts')
    expect(routes).toContain("sub === 'injection-log'")
    expect(routes).toContain('handleInjectionLog(')
    expect(routes).toContain("sub === 'isolation-log'")
    expect(routes).toContain('handleIsolationLog(')
    expect(read('http/routers/injection.ts')).toContain('return { handleInjectionLog }')
    expect(read('http/routers/isolation.ts')).toContain('return { handleIsolationLog }')
  })

  it('C-5 调用方收敛：NodePanelInput 仅渲染器使用，面板侧零 injection/isolation', () => {
    const allowed = new Set(['client/node-panel.ts', 'client/conversation-progress.ts'])
    const hits = walkTs(SRC)
      .filter((p) => readFileSync(p, 'utf8').includes('NodePanelInput'))
      .map((p) => p.slice(SRC.length))
    expect(hits).toContain('client/node-panel.ts')
    expect(hits.filter((h) => !allowed.has(h))).toEqual([])
    // 面板侧两文件不再出现入参/类型字样（大小写敏感，避免误报英文散文）
    expect(read('client/node-panel.ts')).not.toMatch(/injection|isolation/)
    expect(read('client/conversation-progress.ts')).not.toMatch(/injection|isolation/)
  })

  it('C-6 非粘滞：一次性交接模块不落 storage / 不进 URL / 不挂 window', () => {
    const sticky = ['localStorage', 'sessionStorage', 'URLSearchParams', 'location.hash', 'location.search', 'window.history', 'document.cookie']
    for (const rel of ['client/board-focus.ts', 'client/board-entry.ts']) {
      for (const token of sticky) expect(read(rel), rel + ' 不应出现 ' + token).not.toContain(token)
    }
  })

  it('C-7 无 schema 变更：REQBOARD_SCHEMA_VERSION 仍导出且为整数（版本值由父卡 git diff 核对）', () => {
    expect(typeof REQBOARD_SCHEMA_VERSION).toBe('number')
    expect(Number.isInteger(REQBOARD_SCHEMA_VERSION)).toBe(true)
  })
})
