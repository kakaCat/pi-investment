// React shim types for client bundle
// react is externalized — never bundled, resolved at runtime by the DSH
// module-loader seed. This shim provides minimal type coverage so TS compiles
// without errors when we import { createElement } from 'react'.

declare module 'react' {
  export function createElement(
    type: string | Function,
    props?: Record<string, any> | null,
    ...children: any[]
  ): any
}

declare module 'react/jsx-runtime' {
  export function jsx(type: any, props: any, key?: any): any
  export function jsxs(type: any, props: any, key?: any): any
}
