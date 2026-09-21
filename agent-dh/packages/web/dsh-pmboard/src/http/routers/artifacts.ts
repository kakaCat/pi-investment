/**
 * Artifacts 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * REQ-b63a7d t3/t4：
 *  ① 文件读取白名单从 <cwd>/docs 放宽到 **<cwd>（工作区根）**——产物清单里大量源码类
 *     产物（packages/**）此前一律被判 403；
 *  ② 路径先过 domain 归一层（normalizeArtifactPath），兼容台账里的仓库根相对
 *     （agent-dh/docs/...）与「工作区内绝对路径」两种存量写法；
 *  ③ 越界语义分档：穿越 / 反斜杠 / 工作区外绝对路径仍 **403**（安全信号不放宽）；
 *     解析后落在工作区外的兄弟仓库路径 → **404 outside_workspace**（不再冒充权限问题）；
 *     伪路径（brace / 通配）→ **404 not_a_file**；工作区内缺失 → 404 not_found。
 *  ④ 新增 POST docs/resolve 批量端点：host 单点判定每个路径的 form/exists/openable，
 *     前端一次请求拿到全部结论——不再逐条预检（控制台零失败请求）。
 *
 * @module dsh-pmboard/http/routers/Artifacts
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import { existsSync, statSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { fmt } from '../../domain/text/fmt.js'
import { dirname, resolve, sep } from 'node:path'
import { normalizeArtifactPath, type ArtifactPathForm } from '../../domain/artifact/ArtifactPath.js'
import type { RouterCtx } from './shared.js'

/** 单个路径的解析结论（批量端点的响应元素）。 */
export interface DocPathVerdict {
  /** 台账里的原始路径 */
  path: string
  /** 归一后的工作区相对路径（伪路径 / 越界为尽力清洗后的原样） */
  normalized: string
  form: ArtifactPathForm
  exists: boolean
  openable: boolean
  /** 不可打开时的原因（直接展示给用户；可打开时省略） */
  reason?: string
  /** 安全拒绝（穿越 / 反斜杠 / 工作区外绝对路径）——单文件接口返 403 */
  forbidden: boolean
  /** 不可打开时的错误码（单文件接口用） */
  code?: 'forbidden' | 'outside_workspace' | 'not_a_file' | 'not_found'
}

export function createArtifactsRouter(ctx: RouterCtx) {
  const { ok, json, badInput, readBody } = ctx

  /** 工作区根（缺省进程 cwd）。 */
  const workspaceRoot = (): string => resolve(ctx.deps.cwd ?? process.cwd())

  const verdict = (raw: string, over: Partial<DocPathVerdict>): DocPathVerdict => ({
    path: raw,
    normalized: raw,
    form: 'outside',
    exists: false,
    openable: false,
    forbidden: false,
    ...over,
  })

  /**
   * 路径 → 结论（**唯一判定处**：单文件接口与批量端点共用，避免两端两套口径）。
   * 纯字符串归一层只回答「像不像工作区路径」，「文件到底在不在」由 fs 回答。
   */
  function classify(rawPath: string): DocPathVerdict {
    const raw = (rawPath ?? "").trim()
    if (raw.length === 0) {
      return verdict(raw, { form: 'pseudo', code: 'not_a_file', reason: '缺少 path 参数' })
    }
    // 反斜杠与 `..` 在归一之前就拦下——不把攻击路径洗白成工作区相对路径
    const BACKSLASH = String.fromCharCode(92)
    if (raw.includes(BACKSLASH) || raw.split('/').some(s => s === '..')) {
      return verdict(raw, { form: 'outside', forbidden: true, code: 'forbidden', reason: '路径含 .. 或反斜杠，已拒绝' })
    }
    const norm = normalizeArtifactPath(raw, workspaceRoot())
    if (norm.form === 'pseudo') {
      return verdict(raw, { normalized: norm.path, form: 'pseudo', code: 'not_a_file', reason: '不是文件路径（brace / 通配写法或空串）' })
    }
    if (norm.form === 'outside') {
      // 工作区之外的绝对路径：保持 403（与放开 allowlist 之前的安全信号一致）
      const isAbs = raw.startsWith('/')
      return verdict(raw, { normalized: norm.path, form: 'outside', forbidden: isAbs, code: isAbs ? 'forbidden' : 'outside_workspace', reason: '路径在工作区之外' })
    }
    const root = workspaceRoot()
    const target = resolve(root, norm.path)
    if (target !== root && !target.startsWith(root + sep)) {
      return verdict(raw, { normalized: norm.path, form: 'outside', forbidden: true, code: 'forbidden', reason: '解析后落在工作区之外' })
    }
    if (existsSync(target) && statSync(target).isFile()) {
      return verdict(raw, { normalized: norm.path, form: 'workspace', exists: true, openable: true })
    }
    // 工作区内不存在：字符串层无法区分「工作区里恰好有个同名目录」与「仓库根下的兄弟仓库」，
    // 故用 fs 在仓库根再探一次——命中即判跨仓（诚实的 outside_workspace，而不是含糊的 403）。
    const parent = dirname(root)
    const sibling = resolve(parent, norm.path)
    if (sibling !== parent && sibling.startsWith(parent + sep) && existsSync(sibling) && statSync(sibling).isFile()) {
      return verdict(raw, { normalized: norm.path, form: 'outside', code: 'outside_workspace', reason: '文件在工作区之外（跨仓路径，本工作区接口不可服务）' })
    }
    return verdict(raw, { normalized: norm.path, form: 'workspace', code: 'not_found', reason: '文件不存在（未落盘或路径错误）' })
  }

  /**
   * GET /dashboard/api/reqboard/file?path=xxx
   * 读取**工作区内**的文件全文（需求详情页「文档记录」打开用）。
   * 安全：只允许相对路径或工作区内绝对路径；禁止 ../ 与反斜杠；解析后必须落在工作区内。
   */
  async function handleFileRead(res: ServerResponse, rawPath: string): Promise<void> {
    const raw = (rawPath ?? "").trim()
    if (raw.length === 0) return badInput('缺少 path 参数')
    const v = classify(raw)
    if (v.openable) {
      try {
        const content = await readFile(resolve(workspaceRoot(), v.normalized), 'utf8')
        return ok(res, { path: v.normalized, content })
      } catch {
        return json(res, 404, { success: false, error: fmt('文件不存在：{path}', { path: raw }), code: 'not_found' })
      }
    }
    const status = v.code === 'forbidden' ? 403 : 404
    return json(res, status, {
      success: false,
      error: v.reason ?? fmt('文件不可打开：{path}', { path: raw }),
      code: v.code ?? 'not_found',
    })
  }

  /**
   * POST /dashboard/api/reqboard/docs/resolve  {paths: string[]}
   * 批量解析文档可打开性（REQ-b63a7d t4）：前端一次请求拿到全部结论，恒 200 →
   * 控制台不再出现任何失败请求；判定口径与 handleFileRead 完全一致（同一 classify）。
   */
  async function handleDocsResolve(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const rawList = Array.isArray(body.paths) ? body.paths : []
    const paths = rawList.filter(f => typeof f === "string").slice(0, 500) as string[]
    const results = paths.map(f => {
      const v = classify(f)
      return {
        path: v.path,
        normalized: v.normalized,
        form: v.form,
        exists: v.exists,
        openable: v.openable,
        ...(v.openable ? {} : { reason: v.reason ?? '文件不可打开' }),
      }
    })
    ok(res, { results })
  }

  return { handleFileRead, handleDocsResolve }
}
