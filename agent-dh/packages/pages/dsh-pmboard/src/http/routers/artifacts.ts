/**
 * Artifacts 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * @module dsh-pmboard/http/routers/Artifacts
 */
import type { ServerResponse } from 'node:http'
import { readFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import type { RouterCtx } from './shared.js'

export function createArtifactsRouter(ctx: RouterCtx) {
  const { ok, json, badInput } = ctx

  /**
   * GET /dashboard/api/reqboard/file?path=xxx
   * 读取工作区 docs/ 下的文档（需求详情页「文档记录」弹窗打开用）。
   * 安全：只允许相对路径、禁止 ../ 与绝对路径、解析后必须落在 docs/ 内。
   */
  async function handleFileRead(res: ServerResponse, rawPath: string): Promise<void> {
    const rel = (rawPath ?? '').trim()
    if (!rel) return badInput('缺少 path 参数')
    if (rel.startsWith('/') || rel.includes('..') || rel.includes('\\')) {
      return json(res, 403, { success: false, error: '仅允许访问工作区 docs/ 目录', code: 'forbidden' })
    }
    const cwd = process.cwd()
    const docsRoot = resolve(cwd, 'docs')
    const target = resolve(cwd, rel)
    if (target !== docsRoot && !target.startsWith(docsRoot + sep)) {
      return json(res, 403, { success: false, error: '仅允许访问工作区 docs/ 目录', code: 'forbidden' })
    }
    try {
      const content = await readFile(target, 'utf8')
      ok(res, { path: rel, content })
    } catch {
      return json(res, 404, { success: false, error: '文件不存在：' + rel, code: 'not_found' })
    }
  }

  return { handleFileRead }
}
