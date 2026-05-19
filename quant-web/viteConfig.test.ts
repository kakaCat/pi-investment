import { describe, expect, it } from 'vitest'
import { DEFAULT_API_TARGET, resolveApiTarget } from './vite.config'

describe('vite api proxy target', () => {
  it('defaults to the Express quant web API', () => {
    expect(DEFAULT_API_TARGET).toBe('http://localhost:3001')
    expect(resolveApiTarget({})).toBe('http://localhost:3001')
  })

  it('allows overriding the API target for legacy or custom backends', () => {
    expect(resolveApiTarget({ VITE_API_TARGET: 'http://127.0.0.1:5001' })).toBe('http://127.0.0.1:5001')
  })
})
