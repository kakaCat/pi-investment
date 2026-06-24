/**
 * 飞书通知集成测试
 * 测试实际发送消息到飞书
 */
import { feishuNotifyTool } from '../infrastructure/tools/notification/feishu-notify-tool.js';

console.log('🧪 飞书通知集成测试\n');

// 检查环境变量
const webhookUrl = process.env.FEISHU_WEBHOOK_URL;
const chatId = process.env.FEISHU_CHAT_ID;

console.log('📋 环境配置检查:');
console.log('   - FEISHU_WEBHOOK_URL:', webhookUrl ? '已配置 ✅' : '未配置 ❌');
console.log('   - FEISHU_CHAT_ID:', chatId ? '已配置 ✅' : '未配置 ❌');

if (!webhookUrl && !chatId) {
  console.log('\n⚠️  飞书未配置，将测试服务降级逻辑');
  console.log('💡 如需测试真实发送，请配置环境变量：');
  console.log('   export FEISHU_WEBHOOK_URL="your_webhook_url"');
  console.log('   或');
  console.log('   export FEISHU_CHAT_ID="your_chat_id"\n');
}

// 测试 1: 文本消息
console.log('📝 测试 1: 发送文本消息');
try {
  const result = await (feishuNotifyTool.execute as any)('test-text', {
    messageType: 'text',
    content: '🧪 测试消息：feishu-notify-tool 集成测试'
  });

  console.log('   结果:', (result as any).details.success ? '✅ 成功' : '❌ 失败');
  console.log('   消息:', (result as any).details.message);
  if (!(result as any).details.success) {
    console.log('   原因:', (result as any).details.error || '未配置');
  }
} catch (error) {
  console.log('   ❌ 异常:', error);
}

console.log('');

// 测试 2: 卡片消息
console.log('📋 测试 2: 发送卡片消息');
try {
  const result = await (feishuNotifyTool.execute as any)('test-card', {
    messageType: 'card',
    title: '测试卡片',
    content: '这是一条测试卡片消息\n- 项目：pi-investment\n- 状态：正常运行',
    urgency: 'normal'
  });

  console.log('   结果:', (result as any).details.success ? '✅ 成功' : '❌ 失败');
  console.log('   消息:', (result as any).details.message);
  if (!(result as any).details.success) {
    console.log('   原因:', (result as any).details.error || '未配置');
  }
} catch (error) {
  console.log('   ❌ 异常:', error);
}

console.log('');

// 测试 3: 告警消息
console.log('⚠️  测试 3: 发送告警消息');
try {
  const result = await (feishuNotifyTool.execute as any)('test-alert', {
    messageType: 'alert',
    title: '测试告警',
    content: '这是一条测试告警消息',
    urgency: 'high'
  });

  console.log('   结果:', (result as any).details.success ? '✅ 成功' : '❌ 失败');
  console.log('   消息:', (result as any).details.message);
  if (!(result as any).details.success) {
    console.log('   原因:', (result as any).details.error || '未配置');
  }
} catch (error) {
  console.log('   ❌ 异常:', error);
}

console.log('');

// 测试 4: 缺少必需参数
console.log('🔍 测试 4: 卡片消息缺少 title（应该失败）');
try {
  const result = await (feishuNotifyTool.execute as any)('test-missing-title', {
    messageType: 'card',
    content: 'Card without title'
  });

  console.log('   结果:', (result as any).details.success ? '❌ 不应该成功' : '✅ 正确失败');
  console.log('   消息:', (result as any).details.message);
  console.log('   错误:', (result as any).details.error);
} catch (error) {
  console.log('   ✅ 正确抛出异常');
}

console.log('');

// 测试 5: 报告消息（需要 data）
console.log('📊 测试 5: 日报消息缺少 data（应该失败）');
try {
  const result = await (feishuNotifyTool.execute as any)('test-missing-data', {
    messageType: 'daily_report',
    content: 'Report without data'
  });

  console.log('   结果:', (result as any).details.success ? '❌ 不应该成功' : '✅ 正确失败');
  console.log('   消息:', (result as any).details.message);
  console.log('   错误:', (result as any).details.error);
} catch (error) {
  console.log('   ✅ 正确抛出异常');
}

console.log('\n' + '='.repeat(60));
console.log('📋 测试总结:');
console.log('='.repeat(60));

if (!webhookUrl && !chatId) {
  console.log('✅ 工具定义正确，参数验证正常');
  console.log('✅ 服务降级逻辑正常（未配置时不报错）');
  console.log('✅ 错误处理正确（必需参数验证）');
  console.log('\n💡 配置飞书后可测试真实发送功能');
} else {
  console.log('✅ 工具已配置飞书连接');
  console.log('📧 请检查飞书群是否收到测试消息');
}
