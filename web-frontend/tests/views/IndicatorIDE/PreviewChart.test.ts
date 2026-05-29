import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PreviewChart from '@/views/IndicatorIDE/PreviewChart.vue'

const chartMock = vi.hoisted(() => ({
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn()
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => chartMock)
}))

describe('PreviewChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
      configurable: true,
      value: 600
    })
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      value: 320
    })
  })

  it('includes buy and sell signal legend entries', async () => {
    mount(PreviewChart, {
      props: {
        klineData: [
          { date: '2026-05-26', open: 10, high: 12, low: 9, close: 11, volume: 1000 }
        ],
        signalSeries: {
          buy: [true],
          sell: [false]
        }
      },
      attachTo: document.body
    })

    await vi.waitFor(() => {
      expect(chartMock.setOption).toHaveBeenCalled()
    })

    const option = chartMock.setOption.mock.calls.at(-1)?.[0]

    expect(option.legend.data).toEqual(expect.arrayContaining(['买入标记', '卖出标记']))
    expect(option.series.map((series: { name: string }) => series.name)).toEqual(
      expect.arrayContaining(['买入标记', '卖出标记'])
    )
  })
})
