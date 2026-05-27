import { describe, it, expect } from 'vitest'
import {
  formatPrice,
  formatSignedCurrency,
  formatPercent,
  formatAmount,
  formatLargeNumber,
  formatVolume,
  formatDate,
  formatDateTime,
  formatTime,
  formatRelativeTime,
  formatStockCode,
  parseStockCode,
  getChangeColor,
  getChangeClass,
  truncate,
  highlight,
  unique,
  groupBy,
  deepClone,
  removeEmpty,
  buildQueryString,
  parseQueryString,
  debounce,
  throttle
} from '@/utils/format'

describe('format.ts - Number Formatting', () => {
  describe('formatPrice', () => {
    it('should format number to fixed decimal places', () => {
      expect(formatPrice(123.456)).toBe('123.46')
      expect(formatPrice(123.456, 3)).toBe('123.456')
    })

    it('should format string number', () => {
      expect(formatPrice('123.456')).toBe('123.46')
    })

    it('should return -- for invalid input', () => {
      expect(formatPrice('invalid')).toBe('--')
      expect(formatPrice(NaN)).toBe('--')
    })
  })

  describe('formatSignedCurrency', () => {
    it('should format positive currency with plus sign', () => {
      expect(formatSignedCurrency(14694.6)).toBe('+¥14,694.6')
    })

    it('should format negative currency with minus sign', () => {
      expect(formatSignedCurrency(-14694.6)).toBe('-¥14,694.6')
    })

    it('should format zero currency without sign', () => {
      expect(formatSignedCurrency(0)).toBe('¥0')
    })
  })

  describe('formatPercent', () => {
    it('should format positive percentage with sign', () => {
      expect(formatPercent(5.5)).toBe('+5.50%')
      expect(formatPercent(10)).toBe('+10.00%')
    })

    it('should format negative percentage', () => {
      expect(formatPercent(-3.5)).toBe('-3.50%')
    })

    it('should format zero percentage', () => {
      expect(formatPercent(0)).toBe('0.00%')
    })

    it('should respect showSign parameter', () => {
      expect(formatPercent(5.5, 2, false)).toBe('5.50%')
    })

    it('should return -- for invalid input', () => {
      expect(formatPercent('invalid')).toBe('--')
    })
  })

  describe('formatAmount', () => {
    it('should format with thousand separators', () => {
      expect(formatAmount(1234567.89)).toBe('1,234,567.89')
      expect(formatAmount(1000)).toBe('1,000.00')
    })

    it('should respect decimal places', () => {
      expect(formatAmount(1234.5, 0)).toBe('1,235')
      expect(formatAmount(1234.567, 3)).toBe('1,234.567')
    })

    it('should return -- for invalid input', () => {
      expect(formatAmount('invalid')).toBe('--')
    })
  })

  describe('formatLargeNumber', () => {
    it('should format numbers in 亿', () => {
      expect(formatLargeNumber(100000000)).toBe('1.00亿')
      expect(formatLargeNumber(250000000)).toBe('2.50亿')
    })

    it('should format numbers in 万', () => {
      expect(formatLargeNumber(10000)).toBe('1.00万')
      expect(formatLargeNumber(50000)).toBe('5.00万')
    })

    it('should format small numbers as is', () => {
      expect(formatLargeNumber(9999)).toBe('9999.00')
      expect(formatLargeNumber(100)).toBe('100.00')
    })

    it('should return -- for invalid input', () => {
      expect(formatLargeNumber('invalid')).toBe('--')
    })
  })

  describe('formatVolume', () => {
    it('should format volume in 亿', () => {
      expect(formatVolume(100000000)).toBe('1.00亿')
    })

    it('should format volume in 万', () => {
      expect(formatVolume(10000)).toBe('1.00万')
    })

    it('should format small volume as string', () => {
      expect(formatVolume(9999)).toBe('9999')
    })

    it('should return -- for invalid input', () => {
      expect(formatVolume('invalid')).toBe('--')
    })
  })
})

describe('format.ts - Date Formatting', () => {
  describe('formatDate', () => {
    it('should format date with default format', () => {
      const result = formatDate('2024-01-01')
      expect(result).toBe('2024-01-01')
    })

    it('should return -- for empty input', () => {
      expect(formatDate('')).toBe('--')
    })
  })

  describe('formatDateTime', () => {
    it('should format datetime', () => {
      const result = formatDateTime('2024-01-01T12:00:00')
      expect(result).toBe('2024-01-01 12:00:00')
    })

    it('should return -- for empty input', () => {
      expect(formatDateTime('')).toBe('--')
    })
  })

  describe('formatTime', () => {
    it('should format time', () => {
      const result = formatTime('2024-01-01T12:00:00')
      expect(result).toBe('12:00:00')
    })

    it('should return -- for empty input', () => {
      expect(formatTime('')).toBe('--')
    })
  })

  describe('formatRelativeTime', () => {
    it('should return -- for empty input', () => {
      expect(formatRelativeTime('')).toBe('--')
    })
  })
})

describe('format.ts - Stock Code Formatting', () => {
  describe('formatStockCode', () => {
    it('should add SH prefix for Shanghai stocks', () => {
      expect(formatStockCode('600000')).toBe('600000.SH')
      expect(formatStockCode('601398')).toBe('601398.SH')
    })

    it('should add SZ prefix for Shenzhen stocks', () => {
      expect(formatStockCode('000001')).toBe('000001.SZ')
      expect(formatStockCode('300750')).toBe('300750.SZ')
    })

    it('should add BJ prefix for Beijing stocks', () => {
      expect(formatStockCode('830799')).toBe('830799.BJ')
      expect(formatStockCode('430017')).toBe('430017.BJ')
    })

    it('should not add prefix if already exists', () => {
      expect(formatStockCode('600000.SH')).toBe('600000.SH')
    })

    it('should return -- for empty input', () => {
      expect(formatStockCode('')).toBe('--')
    })
  })

  describe('parseStockCode', () => {
    it('should remove market prefix', () => {
      expect(parseStockCode('600000.SH')).toBe('600000')
      expect(parseStockCode('000001.SZ')).toBe('000001')
    })

    it('should return code without prefix as is', () => {
      expect(parseStockCode('600000')).toBe('600000')
    })

    it('should return empty string for empty input', () => {
      expect(parseStockCode('')).toBe('')
    })
  })
})

describe('format.ts - Color Utilities', () => {
  describe('getChangeColor', () => {
    it('should return success for positive values', () => {
      expect(getChangeColor(1)).toBe('success')
      expect(getChangeColor(0.01)).toBe('success')
    })

    it('should return danger for negative values', () => {
      expect(getChangeColor(-1)).toBe('danger')
      expect(getChangeColor(-0.01)).toBe('danger')
    })

    it('should return info for zero', () => {
      expect(getChangeColor(0)).toBe('info')
    })
  })

  describe('getChangeClass', () => {
    it('should return green class for positive values', () => {
      expect(getChangeClass(1)).toBe('text-green-600')
    })

    it('should return red class for negative values', () => {
      expect(getChangeClass(-1)).toBe('text-red-600')
    })

    it('should return gray class for zero', () => {
      expect(getChangeClass(0)).toBe('text-gray-600')
    })
  })
})

describe('format.ts - Text Utilities', () => {
  describe('truncate', () => {
    it('should truncate long text', () => {
      expect(truncate('Hello World', 5)).toBe('Hello...')
    })

    it('should not truncate short text', () => {
      expect(truncate('Hello', 10)).toBe('Hello')
    })

    it('should return empty string for empty input', () => {
      expect(truncate('', 5)).toBe('')
    })
  })

  describe('highlight', () => {
    it('should highlight keyword', () => {
      expect(highlight('Hello World', 'World')).toBe('Hello <mark>World</mark>')
    })

    it('should be case insensitive', () => {
      expect(highlight('Hello World', 'world')).toBe('Hello <mark>World</mark>')
    })

    it('should return original text if no keyword', () => {
      expect(highlight('Hello World', '')).toBe('Hello World')
    })
  })
})

describe('format.ts - Array Utilities', () => {
  describe('unique', () => {
    it('should remove duplicates', () => {
      expect(unique([1, 2, 2, 3, 3, 3])).toEqual([1, 2, 3])
      expect(unique(['a', 'b', 'a', 'c'])).toEqual(['a', 'b', 'c'])
    })

    it('should handle empty array', () => {
      expect(unique([])).toEqual([])
    })
  })

  describe('groupBy', () => {
    it('should group array by key', () => {
      const data = [
        { type: 'A', value: 1 },
        { type: 'B', value: 2 },
        { type: 'A', value: 3 }
      ]
      const result = groupBy(data, 'type')
      expect(result).toEqual({
        A: [
          { type: 'A', value: 1 },
          { type: 'A', value: 3 }
        ],
        B: [{ type: 'B', value: 2 }]
      })
    })
  })
})

describe('format.ts - Object Utilities', () => {
  describe('deepClone', () => {
    it('should deep clone object', () => {
      const obj = { a: 1, b: { c: 2 } }
      const cloned = deepClone(obj)
      expect(cloned).toEqual(obj)
      expect(cloned).not.toBe(obj)
      expect(cloned.b).not.toBe(obj.b)
    })

    it('should deep clone array', () => {
      const arr = [1, [2, 3]]
      const cloned = deepClone(arr)
      expect(cloned).toEqual(arr)
      expect(cloned).not.toBe(arr)
    })
  })

  describe('removeEmpty', () => {
    it('should remove null, undefined, and empty string', () => {
      const obj = {
        a: 1,
        b: null,
        c: undefined,
        d: '',
        e: 0,
        f: false
      }
      expect(removeEmpty(obj)).toEqual({ a: 1, e: 0, f: false })
    })
  })
})

describe('format.ts - URL Utilities', () => {
  describe('buildQueryString', () => {
    it('should build query string from object', () => {
      const params = { a: 1, b: 'test', c: true }
      const result = buildQueryString(params)
      expect(result).toBe('a=1&b=test&c=true')
    })

    it('should remove empty values', () => {
      const params = { a: 1, b: '', c: null }
      const result = buildQueryString(params)
      expect(result).toBe('a=1')
    })
  })

  describe('parseQueryString', () => {
    it('should parse query string to object', () => {
      const result = parseQueryString('a=1&b=test&c=true')
      expect(result).toEqual({ a: '1', b: 'test', c: 'true' })
    })

    it('should handle empty query string', () => {
      const result = parseQueryString('')
      expect(result).toEqual({})
    })
  })
})

describe('format.ts - Debounce and Throttle', () => {
  describe('debounce', () => {
    it('should debounce function calls', async () => {
      let count = 0
      const fn = debounce(() => count++, 100)

      fn()
      fn()
      fn()

      expect(count).toBe(0)

      await new Promise(resolve => setTimeout(resolve, 150))
      expect(count).toBe(1)
    })
  })

  describe('throttle', () => {
    it('should throttle function calls', async () => {
      let count = 0
      const fn = throttle(() => count++, 100)

      fn()
      expect(count).toBe(1)

      fn()
      expect(count).toBe(1)

      await new Promise(resolve => setTimeout(resolve, 150))
      fn()
      expect(count).toBe(2)
    })
  })
})
