/**
 * 竖向布局「同层不折行」回归（REQ-260929010300-dbf9 · 用户 2026-09-29 裁定 C）。
 *
 * serves: FR-6
 *
 * 背景：`calculateLayout` 的竖向分支原先按容器宽度折行
 * （`cols = floor((availW - PAD*2 - GUTTER + GAP_X) / (CARD_W + GAP_X))`）——会话右上角节点面板
 * 的可用宽度约 666px，算得 `cols = 2`，于是同一层的 3 张卡被折成两行，看起来"没有展开"。
 * 用户裁定：**去掉这个限制** —— 每层始终一行，画布按最宽层展开，容器窄时横向滚动。
 *
 * 本文件钉住新口径：①同层所有卡同 y、x 逐张递增；②画布宽度 = 最宽层所需宽度；
 * ③窄内容仍铺满容器（availW 降级为"最小宽度"）。
 */
import { describe, it, expect } from 'vitest'
import { CARD_W, CARD_H, GAP_X, GAP_Y, GUTTER, PAD, calculateLayout } from '../src/client/dag/dag-layout.js'
import { Phase, Role, Side, Status, type CardData } from '../src/client/dag/card-types.js'

const card = (id: string, layer: number): CardData => ({
  id,
  title: id,
  phase: Phase.IMPLEMENT,
  side: Side.BACKEND,
  role: Role.SOLO,
  status: Status.TODO,
  dependsOn: [],
  layer,
})

describe('竖向布局：同层不折行（2026-09-29 裁定 C）', () => {
  it('同层 5 张卡 + 可用宽度 690（旧口径会折成 2 列）→ 一行排开、同 y、x 逐张递增', () => {
    const tasks = [1, 2, 3, 4, 5].map((i) => card('t' + i, 0))
    const l = calculateLayout(tasks, 'vertical', 690)
    const ys = tasks.map((t) => l.pos[t.id]!.y)
    const xs = tasks.map((t) => l.pos[t.id]!.x)
    expect(new Set(ys).size).toBe(1) // 同一行
    expect(xs).toEqual([0, 1, 2, 3, 4].map((i) => PAD + GUTTER + i * (CARD_W + GAP_X)))
    expect(l.width).toBe(PAD * 2 + GUTTER + 5 * (CARD_W + GAP_X) - GAP_X)
    expect(l.width).toBeGreaterThan(690) // 画布比容器宽 → 交给 wrap 横向滚动
  })

  it('窄内容仍铺满容器：availW 作为画布最小宽度', () => {
    const l = calculateLayout([card('a', 0), card('b', 1)], 'vertical', 800)
    expect(l.width).toBe(800)
  })

  it('跨层：每层一行，行距 = CARD_H + BAND_GAP（层内不再出现 +CARD_H+GAP_Y 的折行偏移）', () => {
    const tasks = [card('a', 0), card('b', 1), card('c', 2)]
    const l = calculateLayout(tasks, 'vertical', 400)
    expect(l.pos['b']!.y - l.pos['a']!.y).toBe(CARD_H + 30)
    expect(l.pos['c']!.y - l.pos['b']!.y).toBe(CARD_H + 30)
    expect(l.pos['a']!.y).toBe(PAD)
  })

  it('纵向布局不再使用 GAP_Y 折行间距（同层卡不会出现 y 偏移）', () => {
    const tasks = [card('a', 0), card('b', 0), card('c', 0), card('d', 0)]
    const l = calculateLayout(tasks, 'vertical', 300)
    expect(l.pos['d']!.y).toBe(l.pos['a']!.y)
    expect(GAP_Y).toBeGreaterThan(0) // 常量仍被横向布局使用，这里只确认竖向不再消费它
  })
})
