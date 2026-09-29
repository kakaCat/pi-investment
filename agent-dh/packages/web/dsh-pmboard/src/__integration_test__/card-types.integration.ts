// card-types 联调测试
import {
  PHASE_COLOR_FAMILIES,
  STAGE_TO_PHASE_COLOR,
  PHASE_COLOR_MAP,
  SIDES,
  SIDE_LABELS,
  SIDE_COLOR_MAP,
  ROLE_LABELS,
  STATUS_COLOR_MAP,
  STATUS_LABELS,
  getPhaseColor,
  getSideColor,
  getStatusColor,
  type PhaseColorFamily,
  type Side,
  type TaskRole,
  type TaskStatus
} from '../domain/card-types.js';

console.log('=== 联调测试：card-types.ts 接口验证 ===\n');

// 测试用例 1: Phase 颜色族系统
console.log('【测试 1】Phase 颜色族系统');
console.log('颜色族数量:', PHASE_COLOR_FAMILIES.length);
console.log('颜色族列表:', PHASE_COLOR_FAMILIES);
console.log('StageKind 映射条目数:', Object.keys(STAGE_TO_PHASE_COLOR).length);
console.log('颜色值映射条目数:', Object.keys(PHASE_COLOR_MAP).length);

// 验证一致性
const phaseFamilyCount = PHASE_COLOR_FAMILIES.length;
const phaseColorCount = Object.keys(PHASE_COLOR_MAP).length;
console.log(`一致性检查: ${phaseFamilyCount} 族 vs ${phaseColorCount} 色 [${phaseFamilyCount === phaseColorCount ? '✅' : '❌'}]`);

// 测试 getPhaseColor 函数
console.log('\ngetPhaseColor 函数测试:');
const testStages = ['dev', 'review', 'test', 'fix'] as const;
testStages.forEach(stage => {
  const color = getPhaseColor(stage);
  const family = STAGE_TO_PHASE_COLOR[stage];
  console.log(`  ${stage} -> ${family} -> ${color}`);
});

// 测试用例 2: Side 类型系统
console.log('\n【测试 2】Side 类型系统');
console.log('Side 数量:', SIDES.length);
console.log('Side 列表:', SIDES);
console.log('Side 标签条目数:', Object.keys(SIDE_LABELS).length);
console.log('Side 颜色条目数:', Object.keys(SIDE_COLOR_MAP).length);

const sideCount = SIDES.length;
const sideLabelCount = Object.keys(SIDE_LABELS).length;
const sideColorCount = Object.keys(SIDE_COLOR_MAP).length;
console.log(`一致性检查: ${sideCount} 项 = ${sideLabelCount} 标签 = ${sideColorCount} 色 [${sideCount === sideLabelCount && sideLabelCount === sideColorCount ? '✅' : '❌'}]`);

// 测试 getSideColor 函数
console.log('\ngetSideColor 函数测试:');
SIDES.forEach(side => {
  const color = getSideColor(side);
  const label = SIDE_LABELS[side];
  console.log(`  ${side} (${label}) -> ${color}`);
});

// 测试用例 3: Role 类型系统
console.log('\n【测试 3】Role 类型系统');
console.log('Role 标签条目数:', Object.keys(ROLE_LABELS).length);
const roles: TaskRole[] = ['parent', 'subtask', 'legacy'];
console.log('Role 标签测试:');
roles.forEach(role => {
  const label = ROLE_LABELS[role];
  console.log(`  ${role} -> ${label}`);
});

// 测试用例 4: Status 类型系统
console.log('\n【测试 4】Status 类型系统');
console.log('Status 颜色条目数:', Object.keys(STATUS_COLOR_MAP).length);
console.log('Status 标签条目数:', Object.keys(STATUS_LABELS).length);

const statusColorCount = Object.keys(STATUS_COLOR_MAP).length;
const statusLabelCount = Object.keys(STATUS_LABELS).length;
console.log(`一致性检查: ${statusColorCount} 色 = ${statusLabelCount} 标签 [${statusColorCount === statusLabelCount ? '✅' : '❌'}]`);

// 测试 getStatusColor 函数
console.log('\ngetStatusColor 函数测试:');
const statuses: TaskStatus[] = ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done', 'canceled'];
statuses.forEach(status => {
  const color = getStatusColor(status);
  const label = STATUS_LABELS[status];
  console.log(`  ${status} (${label}) -> ${color}`);
});

// 综合验证
console.log('\n【综合验证】');
const allChecks = [
  { name: 'Phase 颜色族完整性', pass: phaseFamilyCount === phaseColorCount },
  { name: 'Side 三表一致性', pass: sideCount === sideLabelCount && sideLabelCount === sideColorCount },
  { name: 'Status 两表一致性', pass: statusColorCount === statusLabelCount },
];

let allPassed = true;
allChecks.forEach(check => {
  console.log(`  ${check.name}: [${check.pass ? '✅' : '❌'}]`);
  allPassed = allPassed && check.pass;
});

console.log(`\n=== 联调测试总结: ${allPassed ? '✅ 全部通过' : '❌ 存在问题'} ===`);

export {};
