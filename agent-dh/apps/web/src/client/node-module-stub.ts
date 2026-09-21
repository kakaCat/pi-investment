/**
 * Browser stand-in for `node:module`. `createRequire` is unreachable in the
 * configured loader path and fails loud if that assumption changes.
 * （对齐 deepseek-harness apps/web/src/node-module-stub.ts）
 */

/** Fail if browser boot reaches Node's module loader. */
export const createRequire = (): never => {
  throw new Error('node:module is not available in the browser')
}

/** Stub default export for namespace-style imports. */
export default {}
