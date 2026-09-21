/**
 * client 构建产物校验。
 *
 * 背景（REQ-31e11f 事故）：构建失败但没阻断发版 → 浏览器继续吃已提交的旧 lib/client.js，
 * 表现是"改了没用"。所以产物必须被断言，退出码非零才算发版失败。
 *
 * 与 pmboard 的差异：本插件的产物小（无 UI 框架），所以阈值按实际量级定，锚点用
 * **字符串字面量**（minify 不改字符串，改的是标识符）。
 */
import { readFileSync, existsSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pkgRoot = join(here, '..')
const bundlePath = join(pkgRoot, 'lib', 'client.js')

const fail = (msg) => {
  console.error('[verify-client] ' + msg)
  process.exit(1)
}

if (!existsSync(bundlePath)) fail('lib/client.js 不存在（wrap-client 未产出）')
const size = statSync(bundlePath).size
if (size < 1_500) fail('lib/client.js 体积异常（' + size + ' bytes），疑似空产物')

const bundle = readFileSync(bundlePath, 'utf8')
const must = [
  '/plugins/events', // 订阅的 SSE 端点
  'dsh-wlv-bar', // 横幅 DOM 类名
  'dsh-wlv-reload-at', // 刷新防抖标记的 sessionStorage key
  '__dshWlvClient', // HMR/重复 apply 的清理句柄
]
const missing = must.filter((k) => !bundle.includes(k))
if (missing.length > 0) fail('产物缺少关键符号：' + missing.join(', '))

console.log('[verify-client] OK  bundle=' + size + ' bytes, 关键符号齐全')
