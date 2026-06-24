/**
 * 自动获取所有可用的群 ID 并保存
 */
import axios from 'axios';
import * as dotenv from 'dotenv';
import * as fs from 'fs';

dotenv.config();

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;

async function saveAllChatIds() {
  try {
    // 获取 token
    const tokenResponse = await axios.post(
      'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
      { app_id: APP_ID, app_secret: APP_SECRET }
    );

    const token = tokenResponse.data.tenant_access_token;
    console.log('✅ Token 获取成功\n');

    // 获取群列表
    const chatsResponse = await axios.get(
      'https://open.feishu.cn/open-apis/im/v1/chats',
      {
        headers: { 'Authorization': `Bearer ${token}` },
        params: { page_size: 50 }
      }
    );

    const chats = chatsResponse.data.data?.items || [];

    if (chats.length === 0) {
      console.log('❌ 没有找到任何群聊');
      console.log('\n请确保：');
      console.log('1. 机器人已添加到群');
      console.log('2. 机器人有查看群列表的权限\n');
      return;
    }

    console.log(`✅ 找到 ${chats.length} 个群聊：\n`);

    chats.forEach((chat: any, index: number) => {
      console.log(`${index + 1}. ${chat.name || '未命名群'}`);
      console.log(`   ID: ${chat.chat_id}`);
      console.log('');
    });

    // 如果只有一个群，自动保存到 .env
    if (chats.length === 1) {
      const chatId = chats[0].chat_id;
      const envPath = '.env';
      let envContent = fs.readFileSync(envPath, 'utf8');

      if (envContent.includes('FEISHU_CHAT_ID=')) {
        envContent = envContent.replace(/FEISHU_CHAT_ID=.*/g, `FEISHU_CHAT_ID=${chatId}`);
      } else {
        envContent += `\nFEISHU_CHAT_ID=${chatId}\n`;
      }

      fs.writeFileSync(envPath, envContent);
      console.log('✅ 已自动保存 FEISHU_CHAT_ID 到 .env 文件\n');
      console.log('现在可以运行测试了：');
      console.log('npx tsx src/scripts/test-feishu-real-send.ts\n');
    } else {
      console.log('请选择一个群的 Chat ID，添加到 .env：');
      console.log('FEISHU_CHAT_ID=oc_...\n');
    }

  } catch (error: any) {
    console.error('❌ 错误:', error.response?.data || error.message);
  }
}

saveAllChatIds();
