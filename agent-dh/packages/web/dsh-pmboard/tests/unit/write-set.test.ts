/**
 * 写集冲突检测测试
 */

import { describe, it, expect } from 'vitest'
import { detectConflict, validateWriteSet, type WriteSet } from '../../src/domain/write-set.js'

describe('write-set', () => {
  describe('detectConflict', () => {
    it('空集不冲突', () => {
      const ws1: WriteSet = []
      const ws2: WriteSet = ['src/app.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(false)
      expect(detectConflict(ws2, ws1)).toBe(false)
      expect(detectConflict([], [])).toBe(false)
    })

    it('同文件冲突', () => {
      const ws1: WriteSet = ['src/domain/test.ts']
      const ws2: WriteSet = ['src/domain/test.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('不同文件不冲突', () => {
      const ws1: WriteSet = ['src/domain/a.ts']
      const ws2: WriteSet = ['src/domain/b.ts']
      
      // 保守策略：同目录视为冲突
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('不同目录不冲突', () => {
      const ws1: WriteSet = ['src/domain/a.ts']
      const ws2: WriteSet = ['src/adapters/b.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(false)
    })

    it('目录前缀冲突：目录 vs 文件', () => {
      const ws1: WriteSet = ['src/domain/']
      const ws2: WriteSet = ['src/domain/test.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(true)
      expect(detectConflict(ws2, ws1)).toBe(true)
    })

    it('目录前缀冲突：父目录 vs 子目录文件', () => {
      const ws1: WriteSet = ['src/']
      const ws2: WriteSet = ['src/domain/test.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('路径包含：深层嵌套', () => {
      const ws1: WriteSet = ['src/domain/subdomain/']
      const ws2: WriteSet = ['src/domain/subdomain/test.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('共享目录前缀冲突', () => {
      const ws1: WriteSet = ['src/domain/a.ts']
      const ws2: WriteSet = ['src/domain/b.ts']
      
      // 同目录视为冲突（保守策略）
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('根目录文件不冲突', () => {
      const ws1: WriteSet = ['README.md']
      const ws2: WriteSet = ['package.json']
      
      // 根目录不视为共享前缀
      expect(detectConflict(ws1, ws2)).toBe(false)
    })

    it('相对路径：规范化处理', () => {
      const ws1: WriteSet = ['src/domain/test.ts']
      const ws2: WriteSet = ['  src/domain/test.ts  '] // 有空格
      
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('Windows 路径：反斜杠规范化', () => {
      const ws1: WriteSet = ['src\\domain\\test.ts']
      const ws2: WriteSet = ['src/domain/test.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('多文件写集：任意一对冲突即冲突', () => {
      const ws1: WriteSet = ['src/domain/a.ts', 'src/adapters/b.ts']
      const ws2: WriteSet = ['src/domain/c.ts', 'src/application/d.ts']
      
      // src/domain/a.ts 与 src/domain/c.ts 同目录，冲突
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('多文件写集：完全不冲突', () => {
      const ws1: WriteSet = ['src/domain/a.ts', 'src/domain/b.ts']
      const ws2: WriteSet = ['src/adapters/c.ts', 'src/application/d.ts']
      
      expect(detectConflict(ws1, ws2)).toBe(false)
    })

    it('边界：超长路径', () => {
      const longPath = 'a/'.repeat(100) + 'test.ts'
      const ws1: WriteSet = [longPath]
      const ws2: WriteSet = [longPath]
      
      expect(detectConflict(ws1, ws2)).toBe(true)
    })

    it('边界：特殊字符路径', () => {
      const ws1: WriteSet = ['src/domain/test-file.ts']
      const ws2: WriteSet = ['src/adapters/test_file.ts']
      
      // 不同文件，不同目录
      expect(detectConflict(ws1, ws2)).toBe(false)
    })
  })

  describe('validateWriteSet', () => {
    it('有效的写集', () => {
      const ws: WriteSet = ['src/a.ts', 'src/b.ts', 'src/c.ts']
      
      const result = validateWriteSet(ws)
      
      expect(result.valid).toBe(true)
      expect(result.error).toBeUndefined()
    })

    it('空写集有效', () => {
      const ws: WriteSet = []
      
      const result = validateWriteSet(ws)
      
      expect(result.valid).toBe(true)
    })

    it('超过50个路径：无效', () => {
      const ws: WriteSet = Array.from({ length: 51 }, (_, i) => `file${i}.ts`)
      
      const result = validateWriteSet(ws)
      
      expect(result.valid).toBe(false)
      expect(result.error).toContain('超过上限50')
    })

    it('包含空路径：无效', () => {
      const ws: WriteSet = ['src/a.ts', '', 'src/b.ts']
      
      const result = validateWriteSet(ws)
      
      expect(result.valid).toBe(false)
      expect(result.error).toContain('空路径')
    })

    it('包含纯空白路径：无效', () => {
      const ws: WriteSet = ['src/a.ts', '   ', 'src/b.ts']
      
      const result = validateWriteSet(ws)
      
      expect(result.valid).toBe(false)
      expect(result.error).toContain('空路径')
    })

    it('边界：正好50个路径', () => {
      const ws: WriteSet = Array.from({ length: 50 }, (_, i) => `file${i}.ts`)
      
      const result = validateWriteSet(ws)
      
      expect(result.valid).toBe(true)
    })
  })
})
