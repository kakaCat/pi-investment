/**
 * 手动验证脚本 - 联调测试（无需 vitest）
 */

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
} from '../../src/domain/card-types.js'

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    console.log('✓', message);
    passed++;
  } else {
    console.log('✗', message);
    failed++;
  }
}

function assertEqual(actual, expected, message) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    console.log('✓', message);
    passed++;
  } else {
    console.log('✗', message);
    console.log('  Expected:', expected);
    console.log('  Actual:', actual);
    failed++;
  }
}

console.log('\n=== 卡片四轴类型系统 - 联调验证 ===\n');

// Phase 维度测试
console.log('【Phase 维度】');
assertEqual(PHASE_COLOR_FAMILIES.length, 7, 'Phase 应有7个颜色族');
assertEqual(STAGE_TO_PHASE_COLOR.dev, 'dev-family', 'dev 应映射到 dev-family');
assertEqual(STAGE_TO_PHASE_COLOR.integrate, 'dev-family', 'integrate 应映射到 dev-family');
assertEqual(PHASE_COLOR_MAP['dev-family'], '#3b82f6', 'dev-family 应为蓝色');
assertEqual(getPhaseColor('integrate'), '#3b82f6', 'integrate 阶段颜色应为蓝色');

// Side 维度测试
console.log('\n【Side 维度】');
assertEqual(SIDES.length, 4, 'Side 应有4种');
assertEqual(SIDE_LABELS.frontend, '前端', 'frontend 标签应为"前端"');
assertEqual(SIDE_COLOR_MAP.frontend, '#3b82f6', 'frontend 应为蓝色');
assertEqual(getSideColor('frontend'), '#3b82f6', 'frontend 颜色应为蓝色');

// Role 维度测试
console.log('\n【Role 维度】');
assertEqual(ROLE_LABELS.parent, '父卡', 'parent 标签应为"父卡"');
assertEqual(ROLE_LABELS.subtask, '子卡', 'subtask 标签应为"子卡"');
assertEqual(ROLE_LABELS.legacy, '存量卡', 'legacy 标签应为"存量卡"');

// Status 维度测试
console.log('\n【Status 维度】');
assertEqual(STATUS_COLOR_MAP.integrating, '#f59e0b', 'integrating 应为橙色');
assertEqual(STATUS_LABELS.integrating, '联调中', 'integrating 标签应为"联调中"');
assertEqual(getStatusColor('integrating'), '#f59e0b', 'integrating 颜色应为橙色');

// 综合场景测试
console.log('\n【综合场景 - 完整卡片四轴查询】');
const card = {
  stage: 'integrate',
  side: 'frontend',
  role: 'parent',
  status: 'integrating',
};

const result = {
  phaseColor: getPhaseColor(card.stage),
  sideColor: getSideColor(card.side),
  sideLabel: SIDE_LABELS[card.side],
  roleLabel: ROLE_LABELS[card.role],
  statusColor: getStatusColor(card.status),
  statusLabel: STATUS_LABELS[card.status],
};

const expected = {
  phaseColor: '#3b82f6',
  sideColor: '#3b82f6',
  sideLabel: '前端',
  roleLabel: '父卡',
  statusColor: '#f59e0b',
  statusLabel: '联调中',
};

assertEqual(result, expected, '完整四轴查询应返回预期结果');

// 输出统计
console.log('\n=== 验证结果 ===');
console.log(`通过: ${passed} 项`);
console.log(`失败: ${failed} 项`);

if (failed === 0) {
  console.log('\n✓ 所有验证通过，接口联调成功！');
  process.exit(0);
} else {
  console.log('\n✗ 部分验证失败');
  process.exit(1);
}
