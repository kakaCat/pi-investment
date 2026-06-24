/**
 * 检查飞书应用配置和权限
 */
import axios from 'axios';
import * as dotenv from 'dotenv';

dotenv.config();

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;

console.log('🔍 飞书应用配置诊断\n');
console.log('='.repeat(60));

async function diagnose() {
  try {
    // 1. 获取 token
    console.log('1️⃣ 测试 APP_ID 和 APP_SECRET...');
    const tokenResponse = await axios.post(
      'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
      {
        app_id: APP_ID,
        app_secret: APP_SECRET
      }
    );

    if (tokenResponse.data.code !== 0) {
      console.log('   ❌ 认证失败:', tokenResponse.data.msg);
      console.log('\n💡 请检查：');
      console.log('   - APP_ID 是否正确');
      console.log('   - APP_SECRET 是否正确');
      console.log('   - 应用是否已启用\n');
      return;
    }

    const token = tokenResponse.data.tenant_access_token;
    console.log('   ✅ 认证成功\n');

    // 2. 获取应用信息
    console.log('2️⃣ 获取应用信息...');
    try {
      const appInfoResponse = await axios.get(
        'https://open.feishu.cn/open-apis/application/v6/app',
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (appInfoResponse.data.code === 0) {
        const app = appInfoResponse.data.data?.app;
        console.log('   ✅ 应用名称:', app?.app_name || '未知');
        console.log('   ✅ 应用状态:', app?.status === 1 ? '已启用' : '未启用');
      }
    } catch (error) {
      console.log('   ⚠️ 无法获取应用信息（可能需要权限）');
    }
    console.log('');

    // 3. 检查权限
    console.log('3️⃣ 检查应用权限...');
    const permissions = [
      { name: 'im:message', desc: '发送消息' },
      { name: 'im:chat', desc: '获取群列表' },
      { name: 'im:message:send_as_bot', desc: '以机器人身份发送' }
    ];

    console.log('   需要的权限：');
    permissions.forEach(p => {
      console.log(`   - ${p.name}: ${p.desc}`);
    });
    console.log('');

    // 4. 获取群列表
    console.log('4️⃣ 获取机器人加入的群...');
    const chatsResponse = await axios.get(
      'https://open.feishu.cn/open-apis/im/v1/chats',
      {
        headers: {
          'Authorization': `Bearer ${token}`
        },
        params: {
          page_size: 50
        }
      }
    );

    if (chatsResponse.data.code !== 0) {
      console.log('   ❌ 获取群列表失败:', chatsResponse.data.msg);
      console.log('\n💡 可能的原因：');
      console.log('   - 应用缺少 im:chat 权限');
      console.log('   - 应用未发布或未启用\n');
      return;
    }

    const chats = chatsResponse.data.data?.items || [];
    console.log(`   机器人已加入 ${chats.length} 个群\n`);

    if (chats.length === 0) {
      console.log('='.repeat(60));
      console.log('❌ 诊断结果：机器人未加入任何群');
      console.log('='.repeat(60));
      console.log('\n📱 解决方案：\n');
      console.log('方式 1: 通过飞书客户端添加（推荐）');
      console.log('---------------------------------------');
      console.log('1. 打开飞书应用');
      console.log('2. 创建或进入一个测试群');
      console.log('3. 点击群设置 → 群机器人 → 添加机器人');
      console.log('4. 搜索你的应用（APP_ID: cli_a9298edc79e1dcb5）');
      console.log('5. 添加到群\n');

      console.log('方式 2: 通过飞书开放平台');
      console.log('---------------------------------------');
      console.log('1. 访问 https://open.feishu.cn/');
      console.log('2. 进入你的应用管理页面');
      console.log('3. 检查应用是否已发布/启用');
      console.log('4. 确认权限配置正确');
      console.log('5. 在群中添加机器人\n');

      console.log('方式 3: 使用 Webhook（更简单）');
      console.log('---------------------------------------');
      console.log('1. 在飞书群中添加"自定义机器人"');
      console.log('2. 复制 Webhook URL');
      console.log('3. 添加到 .env: FEISHU_WEBHOOK_URL=...');
      console.log('4. 运行: npx tsx src/scripts/test-feishu-integration.ts\n');

    } else {
      console.log('='.repeat(60));
      console.log('✅ 诊断结果：配置正常');
      console.log('='.repeat(60));
      console.log('\n找到以下群：\n');
      chats.forEach((chat: any, index: number) => {
        console.log(`${index + 1}. ${chat.name || '未命名群'}`);
        console.log(`   ID: ${chat.chat_id}`);
        console.log('');
      });
    }

  } catch (error: any) {
    console.log('\n❌ 诊断失败:', error.response?.data || error.message);
  }
}

diagnose();
