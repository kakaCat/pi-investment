/**
 * 通用 HTTP 助手 —— host 半路由共享。
 *
 * @module page-kit/host/http
 */
import type { IncomingMessage, ServerResponse } from 'node:http'

export function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  res.end(text)
}

export function readBody(req: IncomingMessage, maxBytes = 64 * 1024): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = ''
    req.on('data', (c) => {
      raw += c
      if (raw.length > maxBytes) { reject(new Error('body too large')); req.destroy() }
    })
    req.on('end', () => {
      if (!raw.trim()) return resolve({})
      try { resolve(JSON.parse(raw)) } catch { reject(new Error('请求体不是合法 JSON')) }
    })
    req.on('error', reject)
  })
}
