/**
 * Minimal ambient types for the react module.
 * The browser bundle never statically bundles react: tsdown externalizes it and
 * the web shell's module-loader seed resolves require('react') at runtime
 * (same mechanism official client bundles like ui-cordis rely on). agent-dh has
 * no @types/react installed; this scoped shim covers exactly what the footer
 * occupant uses. Treat as internal to this package.
 */
declare module 'react' {
  export type ReactNode = unknown
  export function createElement(
    type: unknown,
    props?: Record<string, unknown> | null,
    ...children: unknown[]
  ): unknown
  export const Fragment: unknown
  export function useState<S>(
    initial: S | (() => S),
  ): [S, (next: S | ((prev: S) => S)) => void]
  export function useEffect(effect: () => void | (() => void), deps?: unknown[]): void
  const _default: {
    createElement: typeof createElement
    Fragment: typeof Fragment
    useState: typeof useState
    useEffect: typeof useEffect
  }
  export default _default
}
