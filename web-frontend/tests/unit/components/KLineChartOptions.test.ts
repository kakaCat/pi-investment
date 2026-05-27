import { describe, expect, it } from 'vitest'
import { buildKLineChartOption, calculateMovingAverage } from '@/components/charts/KLineChart/chart-options'
import type { KLineData } from '@/types/models'

const sampleData: KLineData[] = [
  { date: '2026-05-06', open: 39, close: 39.84, low: 39, high: 40.61, volume: 0, amount: 15071 },
  { date: '2026-05-07', open: 39.94, close: 40.72, low: 39.53, high: 41.1, volume: 0, amount: 15666 },
  { date: '2026-05-08', open: 41.14, close: 41.88, low: 41.09, high: 43.36, volume: 0, amount: 21329 },
  { date: '2026-05-11', open: 41.88, close: 45, low: 41.3, high: 45.35, volume: 0, amount: 29554 },
  { date: '2026-05-12', open: 45.01, close: 43.18, low: 43.1, high: 45.78, volume: 0, amount: 21097 }
]

describe('KLineChart options', () => {
  it('uses terminal dark styling without heavy split areas', () => {
    const option = buildKLineChartOption({ data: sampleData, signals: [], showVolume: true }) as any

    expect(option.backgroundColor).toBe('#0f141d')
    expect(option.grid[0]).toMatchObject({ right: 70, height: '64%' })
    expect(option.yAxis[0].position).toBe('right')
    expect(option.yAxis[0].splitArea.show).toBe(false)
    expect(option.series[0].itemStyle.color).toBe('#ef5350')
    expect(option.series[0].itemStyle.color0).toBe('#26a69a')
  })

  it('falls back to amount bars when volume is unavailable', () => {
    const option = buildKLineChartOption({ data: sampleData, signals: [], showVolume: true }) as any
    const amountSeries = option.series.find((series: any) => series.name === '成交额')

    expect(amountSeries).toBeTruthy()
    expect(amountSeries.data).toEqual([15071, 15666, 21329, 29554, 21097])
  })

  it('keeps MA values aligned with source dates', () => {
    expect(calculateMovingAverage(sampleData, 5)).toEqual([null, null, null, null, 42.12])
  })
})
