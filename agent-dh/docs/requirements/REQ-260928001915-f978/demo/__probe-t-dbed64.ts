
/**
 * 联调探针 t-dbed64：逐接口给出「请求样例 → 期望响应 → 实际返回」。
 */
import {
  validateQueueFile, resolveTasks, renderDagHtml, createDagViewer,
  findCriticalPath, detectCycle, calculateLayout, hitTest,
  type DagData, type DagState,
} from './integration';
import type { CardData } from './card-types';

let pass = 0, fail = 0;
const tables: string[] = [];
function row(name: string, req: string, exp: string, act: string): void {
  const ok = exp === act;
  if (ok) pass++; else fail++;
  tables.push([ok ? 'PASS' : 'FAIL', name, req, exp, act].join(' | '));
}

/* ---------- 请求样例：6 卡真实形态队列（父卡+2 子卡+3 独立卡） ---------- */
const Q = {
  requirement_id: 'REQ-PROBE',
  tasks: [
    { id: 'tA',  title: '父卡',       phase: 'implement', side: 'backend',   status: 'done',        layer: 0, dependsOn: [], requirementId: 'REQ-PROBE' },
    { id: 'tA1', title: '父卡·研发', phase: 'implement', side: 'backend',   status: 'done',        layer: 0, dependsOn: [], parentId: 'tA', stageKind: 'dev',       requirementId: 'REQ-PROBE' },
    { id: 'tA2', title: '父卡·联调', phase: 'implement', side: 'backend',   status: 'in_progress', layer: 1, dependsOn: ['tA1'], parentId: 'tA', stageKind: 'integrate', requirementId: 'REQ-PROBE' },
    { id: 'tB',  title: 'B',         phase: 'test',      side: 'fullstack', status: 'todo',        layer: 1, dependsOn: ['tA'], requirementId: 'REQ-PROBE' },
    { id: 'tC',  title: 'C',         phase: 'doc',       side: 'doc',       status: 'done',        layer: 1, dependsOn: ['tA'], requirementId: 'REQ-PROBE' },
    { id: 'tD',  title: 'D',         phase: 'merge',     side: 'fullstack', status: 'todo',        layer: 2, dependsOn: ['tB'], requirementId: 'REQ-PROBE' },
  ] as CardData[],
  edges: [ {from:'tA',to:'tB'}, {from:'tA',to:'tC'}, {from:'tA1',to:'tA2'}, {from:'tB',to:'tD'} ],
  ready: ['tB'],
};
const STATE: DagState = { dir: 'vertical', crit: false, focus: false, pinned: null };

/* ---------- I1 validateQueueFile ---------- */
const v = validateQueueFile(Q);
row('I1 validateQueueFile', JSON.stringify({requirement_id:'REQ-PROBE',tasks:6,edges:4,ready:1}),
    'passed=true issues=0', 'passed=' + v.passed + ' issues=' + v.issues.length);

/* ---------- I2 resolveTasks（FR-1） ---------- */
const R = resolveTasks(Q.tasks);
const counts = { parent: R.filter(t=>t.role==='parent').length, child: R.filter(t=>t.role==='child').length, solo: R.filter(t=>t.role==='solo').length };
row('I2 resolveTasks roles', 'tasks=6(parentId x2)',
    'parent=1 child=2 solo=3', 'parent='+counts.parent+' child='+counts.child+' solo='+counts.solo);
const pA = R.filter(t=>t.id==='tA')[0]!;
row('I2 resolveTasks kids', 'tA 的子卡',
    'kids=[tA1,tA2]', 'kids=['+(pA.kids||[]).map(k=>k.id).join(',')+']');

/* ---------- I3 findCriticalPath（FR-6） ---------- */
const crit = findCriticalPath(Q.tasks);
// 契约返回 Set<string>，迭代顺序无约定 → 按集合语义比较（实测回溯序为 tD,tB,tA）
row('I3 findCriticalPath', 'longest path of 4 edges（集合语义）',
    'size=3 {tA,tB,tD}', 'size='+crit.size+' {'+Array.from(crit).sort().join(',')+'}');
row('I3 detectCycle', '无环队列', 'null', String(detectCycle(Q.tasks)));

/* ---------- I4 renderDagHtml（FR-2/3/4/7） ---------- */
const dag: DagData = { tasks: Q.tasks, edges: Q.edges, ready: Q.ready };
const html = renderDagHtml(dag, STATE);
const cnt = (s:string, re:RegExp)=> (s.match(re)||[]).length;
row('I4 renderDagHtml nodes', 'vertical, focus=false', '6', String(cnt(html,/class="node/g)));
row('I4 renderDagHtml cards', 'vertical, focus=false', '6', String(cnt(html,/class="card"/g)));
row('I4 renderDagHtml paths', 'edges=4', '4', String(cnt(html,/data-from="/g)));
row('I4 renderDagHtml e-crit', 'crit={tA,tB,tD}', '2', String(cnt(html,/class="e-crit"/g)));
row('I4 renderDagHtml e-done', 'tA(完成)->tC(完成)', '1', String(cnt(html,/class="e-done"/g)));
row('I4 renderDagHtml chain', 'parent=1', '1', String(cnt(html,/card-chain/g)));
row('I4 renderDagHtml ready-dot', 'ready=1', '1', String(cnt(html,/ready-dot/g)));
const fHtml = renderDagHtml(dag, { ...STATE, focus: true });
row('I4 renderDagHtml focus', 'focus=true', 'nodes=3 paths=2',
    'nodes='+cnt(fHtml,/class="node/g)+' paths='+cnt(fHtml,/data-from="/g));

/* ---------- I5 布局 / 命中测试（FR-3） ---------- */
const lay = calculateLayout(Q.tasks, 'vertical', 690);
row('I5 calculateLayout pos', 'vertical, availW=690', 'pos=6', 'pos='+Object.keys(lay.pos).length);
const p0 = lay.pos['tA']!;
row('I5 hitTest 命中', 'tA 卡心 ('+(p0.x+30)+','+(p0.y+30)+')', 'tA', String(hitTest(lay, p0.x+30, p0.y+30, 0)));
row('I5 hitTest 空白', '(-5,-5)', 'null', String(hitTest(lay, -5, -5, 0)));

/* ---------- I6 降级路径 ---------- */
const cyc = [
  { id:'x', title:'X', phase:'implement', side:'backend', role:'solo', status:'todo', dependsOn:['z'], layer:0 },
  { id:'y', title:'Y', phase:'implement', side:'backend', role:'solo', status:'todo', dependsOn:['x'], layer:1 },
  { id:'z', title:'Z', phase:'implement', side:'backend', role:'solo', status:'todo', dependsOn:['y'], layer:2 },
] as CardData[];
row('I6 有环降级', 'x->y->z->x', '含“循环依赖”',
    renderDagHtml({tasks:cyc,edges:[],ready:[]}, STATE).indexOf('循环依赖')>=0 ? '含“循环依赖”' : '缺失');
row('I6 空图降级', 'tasks=[]', '含“暂无任务”',
    renderDagHtml({tasks:[],edges:[],ready:[]}, STATE).indexOf('暂无任务')>=0 ? '含“暂无任务”' : '缺失');
const bad = validateQueueFile({ requirement_id:'REQ-X',
  tasks:[{ id:'t1', title:'T1', phase:'implement', side:'backend', role:'solo', status:'todo', layer:0, dependsOn:[], requirementId:'REQ-Y' } as CardData],
  edges:[{from:'t1',to:'t-ghost'}], ready:['t1','t-ghost'] });
row('I6 坏数据校验', 'V-2 悬空边 / V-3 串档 / V-6 非法 ready', 'V-2,V-3,V-6',
    Array.from(new Set(bad.issues.map(i=>i.rule))).sort().join(','));

/* ---------- I7 createDagViewer（FR-5） ---------- */
interface FakeCanvas { width:number; height:number; style:Record<string,string>; parentElement:{clientWidth:number};
  getContext():unknown; getBoundingClientRect():{left:number;top:number;width:number;height:number};
  addEventListener(t:string,f:(e:unknown)=>void):void; removeEventListener(t:string,f:(e:unknown)=>void):void; hasListener(t:string):boolean; }
function mkCanvas():FakeCanvas {
  const ls:Record<string,Array<(e:unknown)=>void>> = {};
  const ctx:any = { globalAlpha:1, fillStyle:'', strokeStyle:'', lineWidth:1, font:'', textAlign:'left', textBaseline:'alphabetic', lineCap:'butt',
    save(){},restore(){},beginPath(){},closePath(){},moveTo(){},lineTo(){},quadraticCurveTo(){},setTransform(){},setLineDash(){},clip(){},clearRect(){},
    bezierCurveTo(){},stroke(){},fill(){},fillRect(){},fillText(){},arc(){},measureText(t:string){return {width:String(t).length*6};} };
  return { width:0,height:0,style:{},parentElement:{clientWidth:690},
    getContext(){return ctx;}, getBoundingClientRect(){return {left:0,top:0,width:900,height:600};},
    addEventListener(t,f){(ls[t]=ls[t]||[]).push(f);}, removeEventListener(t,f){ls[t]=(ls[t]||[]).filter(x=>x!==f);},
    hasListener(t){return (ls[t]||[]).length>0;} };
}
const canvas = mkCanvas();
let err:string|null = null;
let viewer:ReturnType<typeof createDagViewer>|null = null;
try { viewer = createDagViewer(canvas as unknown as HTMLCanvasElement, dag, { dir:'vertical' }); } catch(e){ err=String((e as Error).message); }
row('I7 createDagViewer', 'vertical + 6 卡', '不抛异常', err===null?'不抛异常':'抛异常:'+err);
if (viewer) {
  const L = viewer.layout()!;
  row('I7 layout 覆盖', '全部任务', 'pos=6', 'pos='+Object.keys(L.pos).length);
  row('I7 事件绑定', 'mousemove/click/mouseleave', '3/3',
      [canvas.hasListener('mousemove'),canvas.hasListener('click'),canvas.hasListener('mouseleave')].filter(Boolean).length+'/3');
  row('I7 patch dir', "patch({dir:'horizontal'})", 'horizontal', viewer.patch({dir:'horizontal'}).layout.dir);
  const fRes = viewer.patch({ dir:'vertical', focus:true });
  row('I7 patch focus', 'patch({focus:true})', 'visible=3', 'visible='+fRes.visibleIds.length);
  viewer.destroy();
  row('I7 destroy', 'destroy()', '解绑=true', '解绑='+(!canvas.hasListener('mousemove')));
}

console.log('| 结果 | 接口 | 请求样例 | 期望响应 | 实际返回 |');
console.log('|---|---|---|---|---|');
tables.forEach(r=>console.log('| '+r+' |'));
console.log('\n联调结果：' + pass + ' 通过 / ' + fail + ' 失败');
process.exit(fail===0?0:1);
