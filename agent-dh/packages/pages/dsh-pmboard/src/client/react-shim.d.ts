/**
 * react 模块的最小环境类型（与 packages/pages/execution 同款做法）。
 *
 * 为什么需要：浏览器包不打包 react——tsdown 把它 externalize，运行时由 DSH web shell
 * 的 module-loader seed 解析 require('react')（官方客户端包如 ui-cordis 同机制）。
 * agent-dh 未安装 @types/react；本 shim 只覆盖本包用到的 API，作用域限于本包。
 */
declare module 'react' {
  export type ReactNode = unknown
  export function createElement(
    type: unknown,
    props?: Record<string, unknown> | null,
    ...children: unknown[]
  ): unknown
  export function useState<S>(
    initial: S | (() => S),
  ): [S, (next: S | ((prev: S) => S)) => void]
  export function useEffect(effect: () => void | (() => void), deps?: unknown[]): void
  export function useRef<T>(initial: T): { current: T }
  export function useCallback<T extends (...args: any[]) => any>(fn: T, deps?: unknown[]): T
  const _default: {
    createElement: typeof createElement
    useState: typeof useState
    useEffect: typeof useEffect
    useRef: typeof useRef
    useCallback: typeof useCallback
  }
  export default _default
}
