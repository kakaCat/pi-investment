import 'dotenv/config';
import * as lark from '@larksuiteoapi/node-sdk';

async function getChatId() {
  const client = new lark.Client({
    appId: process.env.FEISHU_APP_ID!,
    appSecret: process.env.FEISHU_APP_SECRET!
  });

  try {
    console.log('🔍 获取飞书群聊列表...\n');

    const result = await client.im.chat.list({
      params: {
        page_size: 20
      }
    });

    if (result.data?.items && result.data.items.length > 0) {
      console.log('找到以下群聊：\n');
      result.data.items.forEach((chat: any, index: number) => {
        console.log(`${index + 1}. ${chat.name || '未命名群聊'}`);
        console.log(`   Chat ID: ${chat.chat_id}`);
        console.log(`   描述: ${chat.description || '无'}\n`);
      });

      console.log('\n💡 将其中一个 Chat ID 添加到 .env 文件：');
      console.log('FEISHU_DEFAULT_CHAT_ID=oc_xxxxxxxxxxxxx');
    } else {
      console.log('❌ 未找到任何群聊');
      console.log('\n请确保：');
      console.log('1. 机器人已被添加到至少一个群聊');
      console.log('2. 应用有 im:chat:readonly 权限');
    }
  } catch (error: any) {
    console.error('❌ 获取失败:', error.message);
    console.log('\n可能的原因：');
    console.log('1. APP_ID 或 APP_SECRET 不正确');
    console.log('2. 应用缺少 im:chat:readonly 权限');
    console.log('3. 网络连接问题');
  }
}

getChatId();
