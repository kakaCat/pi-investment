/**
 * 文件资源地址构造 —— 对齐 DSH 官方 grammar（REQ-ff20ca t5）。
 *
 * 官方出处：@deepseek-ai/dsh-util-workspace-path 的 file-address 模块
 * （FILE_ADDRESS_PREFIX / encodeSegment / encodePath / sessionFileAddress）。
 * 本地实现而非新增依赖：零依赖（不需要 pnpm install，规避依赖链接漂移）；
 * grammar 已冻结，用单测锁定；上游如有变更按此同步并补测试。
 *
 * @module dsh-pmboard/client/file-address
 */

/** 所有文件地址的前缀（与官方一致）。 */
const FILE_ADDRESS_PREFIX = 'dsh-resource://file/'

/** 编码单个 id/路径段；保留 ":"（盘符）字面量——与官方 encodeSegment 一致。 */
function encodeSegment(segment: string): string {
  return encodeURIComponent(segment).replace(/%3A/gi, ':')
}

/** 逐段编码 "/" 分隔的路径。 */
function encodePath(path: string): string {
  return path.split('/').map(encodeSegment).join('/')
}

/**
 * 构造经某个 Session 读取的文件地址。
 *
 * 与官方 sessionFileAddress 同形：反斜杠归一为 "/"，去掉前导 "./"，
 * 产物为 `dsh-resource://file/session/<sessionId>/<path>`。
 */
export function sessionFileAddress(sessionId: string, path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/^(?:\.\/)+/, '')
  return `${FILE_ADDRESS_PREFIX}session/${encodeSegment(sessionId)}/${encodePath(normalized)}`
}
