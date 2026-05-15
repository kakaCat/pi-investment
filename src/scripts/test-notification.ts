import 'dotenv/config';
import { NotificationService } from '../services/notification/notification-service.js';
import { FeishuChannel } from '../services/notification/feishu-channel.js';

async function main() {
  console.log('🧪 飞书通知系统测试\n');

  // 检查环境变量
  const appId = process.env.FEISHU_APP_ID;
  const appSecret = process.env.FEISHU_APP_SECRET;
  const chatId = process.env.FEISHU_DEFAULT_CHAT_ID;

  if (!appId || !appSecret || !chatId) {
    console.error('❌ 缺少必要的环境变量:');
    console.error('   FEISHU_APP_ID:', appId ? '✓' : '✗');
    console.error('   FEISHU_APP_SECRET:', appSecret ? '✓' : '✗');
    console.error('   FEISHU_DEFAULT_CHAT_ID:', chatId ? '✓' : '✗');
    process.exit(1);
  }

  console.log('✅ 环境变量检查通过\n');

  // 初始化服务
  const service = new NotificationService();
  const feishuChannel = new FeishuChannel({
    appId,
    appSecret,
    defaultChatId: chatId
  });

  service.registerChannel('feishu', feishuChannel);

  console.log('✅ 通知服务初始化完成\n');

  // 测试 1: 文本消息
  console.log('📤 测试 1: 发送文本消息...');
  try {
    await service.send('🧪 测试消息 - 飞书通知系统正常运行');
    console.log('✅ 文本消息发送成功\n');
  } catch (error) {
    console.error('❌ 文本消息发送失败:', error);
    process.exit(1);
  }

  // 等待 2 秒
  await new Promise(resolve => setTimeout(resolve, 2000));

  // 测试 2: 卡片消息
  console.log('📤 测试 2: 发送卡片消息...');
  try {
    await service.sendCard({
      title: '🧪 测试卡片',
      content: '**这是一条测试卡片消息**\n\n包含 Markdown 格式:\n- 列表项 1\n- 列表项 2\n\n`代码块`',
      type: 'card',
      metadata: { test: true }
    });
    console.log('✅ 卡片消息发送成功\n');
  } catch (error) {
    console.error('❌ 卡片消息发送失败:', error);
    process.exit(1);
  }

  // 等待 2 秒
  await new Promise(resolve => setTimeout(resolve, 2000));

  // 测试 3: 交易信号格式
  console.log('📤 测试 3: 发送交易信号格式...');
  try {
    await service.sendCard({
      title: '🟢 买入信号',
      content: `🟢 **贵州茅台** (600519)

**当前价:** ¥1850
**置信度:** 85%

**分析理由**
技术面突破关键阻力位，成交量放大，MACD 金叉形成。基本面稳健，业绩持续增长。`,
      type: 'card',
      metadata: {
        signal_type: 'buy',
        symbol: '600519',
        price: 1850,
        confidence: 0.85
      }
    });
    console.log('✅ 交易信号发送成功\n');
  } catch (error) {
    console.error('❌ 交易信号发送失败:', error);
    process.exit(1);
  }

  console.log('🎉 所有测试通过！');
  console.log('\n请检查飞书群聊，确认收到 3 条测试消息。');
}

main().catch(error => {
  console.error('❌ 测试失败:', error);
  process.exit(1);
});
