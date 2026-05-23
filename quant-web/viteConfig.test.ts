import { describe, expect, it } from 'vitest'
import { DEFAULT_API_TARGET, resolveApiTarget } from './vite.config'

describe('vite api proxy target', () => {
  it('defaults to the Python quant API', () => {
    expect(DEFAULT_API_TARGET).toBe('http://127.0.0.1:5002')
    expect(resolveApiTarget({})).toBe('http://127.0.0.1:5002')
  })

  it('allows overriding the API target for custom backends', () => {
    expect(resolveApiTarget({ VITE_API_TARGET: 'http://127.0.0.1:3001' })).toBe('http://127.0.0.1:3001')
  })
})
