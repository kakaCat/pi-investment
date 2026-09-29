/**
 * dag-layout.ts 单测（REQ-260928001915-f978 · t-4256bf · FR-3 · t-c11c61 研发）
 *
 * 运行（无需浏览器 / 无第三方依赖）：
 *   cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/dag-layout.test.ts
 *
 * 覆盖 FR-3 的四条硬约束 + 一条回归：
 *   ① 12 卡 3 层 → 每个节点都有 (x, y)
 *   ② 纵向：层级从上到下；同层不折行时同层 y 相同，折行时行内 y 相同且满行
 *   ③ 横向：层级从左到右；同层 x 相同（每层 ≤ MAX_ROWS 卡）
 *   ④ 画布尺寸按节点数与方向自适应
 *   ⑤ 回归：布局是纯函数——不得写回/污染调用方的任务对象（曾用 _bary）
 *
 * 退出码 0 = 全绿；1 = 有断言失败。
 */
import {
  CARD_W,
  CARD_H,
  GAP_X,
  GAP_Y,
  PAD,
  GUTTER,
  MAX_ROWS,
  calculateLayout,
  hitTest,
  type LayoutResult,
} from './dag-layout';
import { Phase, Side, Role, Status, type CardData } from './card-types';

let pass = 0;
let fail = 0;
const failures: string[] = [];

function check(name: string, cond: boolean, detail?: string): void {
  if (cond) {
    pass += 1;
    console.log('  ok   ' + name);
  } else {
    fail += 1;
    failures.push(name + (detail ? ' — ' + detail : ''));
    console.log('  FAIL ' + name + (detail ? ' — ' + detail : ''));
  }
}

function card(id: string, layer: number, dependsOn?: string[]): CardData {
  return {
    id,
    title: '任务 ' + id,
    phase: Phase.IMPLEMENT,
    side: Side.FRONTEND,
    role: Role.SOLO,
    status: Status.TODO,
    layer,
    dependsOn,
  };
}

/* ---------------- 12 卡 3 层：验收数据集 ---------------- */
const tasks12: CardData[] = [
  card('a1', 0), card('a2', 0), card('a3', 0), card('a4', 0),
  card('b1', 1, ['a1']), card('b2', 1, ['a1', 'a2']), card('b3', 1, ['a2']), card('b4', 1, ['a3', 'a4']),
  card('c1', 2, ['b1']), card('c2', 2, ['b2']), card('c3', 2, ['b3']), card('c4', 2, ['b4']),
];

console.log('\n[1] 节点坐标完备性（12 卡 3 层）');
const vWide = calculateLayout(tasks12, 'vertical', PAD * 2 + GUTTER + 4 * (CARD_W + GAP_X) + 100);
const vNarrow = calculateLayout(tasks12, 'vertical', 900);
const h = calculateLayout(tasks12, 'horizontal', 900);
check('纵向：12 个节点全部有坐标', Object.keys(vWide.pos).length === 12, 'got=' + Object.keys(vWide.pos).length);
check('横向：12 个节点全部有坐标', Object.keys(h.pos).length === 12, 'got=' + Object.keys(h.pos).length);
check('返回 dir 与请求一致', vWide.dir === 'vertical' && h.dir === 'horizontal');

console.log('\n[2] 纵向：层级从上到下 + 同层折行');
check('纵向：层号越大 y 越大', vWide.bands.every((b, i) => i === 0 || b.y > vWide.bands[i - 1].y));
check('纵向：band 数与层数一致（3 层）', vWide.bands.length === 3, 'got=' + vWide.bands.length);
check('纵向：画布够宽时同层 y 相同', (() => {
  const ys = new Set(tasks12.filter(t => t.layer === 0).map(t => vWide.pos[t.id].y));
  return ys.size === 1;
})());
check('纵向：窄画布(900)同层折行，行内 y 相同且除末行外满行', (() => {
  const byLayer: Record<number, number[]> = {};
  tasks12.forEach(t => { (byLayer[t.layer] = byLayer[t.layer] || []).push(vNarrow.pos[t.id].y); });
  return Object.keys(byLayer).every(l => {
    const rows: Record<number, number> = {};
    byLayer[Number(l)].forEach(y => { rows[y] = (rows[y] || 0) + 1; });
    const counts = Object.keys(rows).map(Number).sort((a, b) => a - b).map(k => rows[k]);
    const maxRow = Math.max(...counts);
    return maxRow >= 1 &&
      counts.slice(0, -1).every(c => c === maxRow) &&
      counts[counts.length - 1] <= maxRow;
  });
})());
check('纵向：窄画布(900)确实发生了折行（每层 4 卡 > 3 列）', (() => {
  const layer0ys = new Set(tasks12.filter(t => t.layer === 0).map(t => vNarrow.pos[t.id].y));
  return layer0ys.size === 2;
})());

console.log('\n[3] 横向：层级从左到右 + 同层纵向堆叠');
check('横向：层号越大 x 越大', h.bands.every((b, i) => i === 0 || h.bands[i - 1] !== undefined) && (() => {
  const xs = h.bands.map(b => Math.min(...tasks12.filter(t => t.layer === b.layer).map(t => h.pos[t.id].x)));
  return xs.every((x, i) => i === 0 || x > xs[i - 1]);
})());
check('横向：同层 x 相同（每层 ≤ MAX_ROWS 卡）', (() => {
  const byLayer: Record<number, Set<number>> = {};
  tasks12.forEach(t => { (byLayer[t.layer] = byLayer[t.layer] || new Set()).add(h.pos[t.id].x); });
  return Object.keys(byLayer).every(l => byLayer[Number(l)].size === 1);
})());
check('横向：同层 y 纵向堆叠（≥2 张卡时 y 互不相同）', (() => {
  const ys = tasks12.filter(t => t.layer === 0).map(t => h.pos[t.id].y);
  return new Set(ys).size === ys.length;
})());
check('横向：MAX_ROWS 生效（层内不超过 8 行）', MAX_ROWS === 8);

console.log('\n[4] 画布尺寸自适应');
check('画布宽高均为正', vWide.width > 0 && vWide.height > 0 && h.width > 0 && h.height > 0);
check('两方向画布尺寸不同', vWide.width !== h.width || vWide.height !== h.height);
check('所有节点落在画布内', (() => {
  const inside = (r: LayoutResult) => Object.keys(r.pos).every(id => {
    const p = r.pos[id];
    return p.x >= 0 && p.y >= 0 && p.x + CARD_W <= r.width && p.y + CARD_H <= r.height;
  });
  return inside(vWide) && inside(vNarrow) && inside(h);
})());

console.log('\n[5] 降级：缺 layer 落到第 0 层');
const noLayer = [card('x1', undefined as unknown as number), card('x2', undefined as unknown as number)];
check('缺 layer 仍全部有坐标', Object.keys(calculateLayout(noLayer, 'vertical', 900).pos).length === 2);
check('缺 layer 视为同一层（y 相同）', (() => {
  const r = calculateLayout(noLayer, 'vertical', 900);
  return r.pos.x1.y === r.pos.x2.y;
})());

console.log('\n[6] hitTest 命中测试');
const target = tasks12[0].id;
const p0 = vWide.pos[target];
check('节点中心命中自身', hitTest(vWide, p0.x + CARD_W / 2, p0.y + CARD_H / 2, 0) === target);
check('画布远处返回 null', hitTest(vWide, -100, -100, 0) === null);
check('inset 容差生效（外扩 10px 后命中）', hitTest(vWide, p0.x - 5, p0.y - 5, 0) === null && hitTest(vWide, p0.x - 5, p0.y - 5, 10) === target);

console.log('\n[7] 纯函数回归（不得污染输入任务对象）');
const snapshot = JSON.stringify(tasks12);
const keysBefore = tasks12.map(t => Object.keys(t).sort().join(','));
const v1 = calculateLayout(tasks12, 'vertical', 900);
const v2 = calculateLayout(tasks12, 'vertical', 900);
check('输入任务对象未被写回（JSON 不变）', JSON.stringify(tasks12) === snapshot);
check('输入任务对象未新增键（无 _bary / 无内部字段泄漏）', tasks12.map(t => Object.keys(t).sort().join(',')).join('|') === keysBefore.join('|'));
check('任务对象上没有 _bary 残留', tasks12.every(t => !('_bary' in (t as unknown as Record<string, unknown>))));
check('传入数组本身未被重排（12 张、顺序不变）', tasks12.length === 12 && tasks12[0].id === 'a1' && tasks12[11].id === 'c4');
check('同输入两次调用输出一致（确定性）', JSON.stringify(v1) === JSON.stringify(v2));

console.log('\n[汇总] ' + pass + ' 通过 / ' + fail + ' 失败');
if (fail > 0) {
  console.error('失败项：\n  - ' + failures.join('\n  - '));
  process.exit(1);
}
console.log('dag-layout 自测全绿。');
