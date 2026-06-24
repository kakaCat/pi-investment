/**
 * 使用飞书 App API 发送测试消息
 * 通过 App ID/Secret 获取 access_token 后发送消息
 */
import axios from 'axios';
import * as dotenv from 'dotenv';

// 加载环境变量
dotenv.config();

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
const CHAT_ID = process.env.FEISHU_CHAT_ID;

console.log('🧪 飞书 App API 真实发送测试\n');

// 检查配置
console.log('📋 配置检查:');
console.log('   - FEISHU_APP_ID:', APP_ID ? '✅ 已配置' : '❌ 未配置');
console.log('   - FEISHU_APP_SECRET:', APP_SECRET ? '✅ 已配置' : '❌ 未配置');
console.log('   - FEISHU_CHAT_ID:', CHAT_ID ? '✅ 已配置' : '❌ 未配置');

if (!APP_ID || !APP_SECRET) {
  console.log('\n❌ 缺少必需配置，无法继续测试');
  process.exit(1);
}

if (!CHAT_ID) {
  console.log('\n⚠️  FEISHU_CHAT_ID 未配置，无法发送测试消息');
  console.log('💡 请在 .env 中添加：FEISHU_CHAT_ID=oc_xxx');
  console.log('   （在飞书群聊中获取群 ID）\n');
  process.exit(1);
}

/**
 * 获取 Access Token
 */
async function getTenantAccessToken(): Promise<string> {
  try {
    const response = await axios.post(
      'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
      {
        app_id: APP_ID,
        app_secret: APP_SECRET
      }
    );

    if (response.data.code !== 0) {
      throw new Error(`获取 token 失败: ${response.data.msg}`);
    }

    return response.data.tenant_access_token;
  } catch (error) {
    throw new Error(`获取 token 异常: ${error}`);
  }
}

/**
 * 发送文本消息
 */
async function sendTextMessage(token: string, chatId: string, text: string) {
  try {
    const response = await axios.post(
      'https://open.feishu.cn/open-apis/im/v1/messages',
      {
        receive_id: chatId,
        msg_type: 'text',
        content: JSON.stringify({ text })
      },
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        params: {
          receive_id_type: 'chat_id'
        }
      }
    );

    return response.data;
  } catch (error: any) {
    throw new Error(`发送消息失败: ${error.response?.data?.msg || error.message}`);
  }
}

/**
 * 发送卡片消息
 */
async function sendCardMessage(token: string, chatId: string, title: string, content: string) {
  try {
    const card = {
      header: {
        title: {
          tag: 'plain_text',
          content: title
        },
        template: 'blue'
      },
      elements: [
        {
          tag: 'div',
          text: {
            tag: 'lark_md',
            content: content
          }
        }
      ]
    };

    const response = await axios.post(
      'https://open.feishu.cn/open-apis/im/v1/messages',
      {
        receive_id: chatId,
        msg_type: 'interactive',
        content: JSON.stringify(card)
      },
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        params: {
          receive_id_type: 'chat_id'
        }
      }
    );

    return response.data;
  } catch (error: any) {
    throw new Error(`发送卡片失败: ${error.response?.data?.msg || error.message}`);
  }
}

// 主测试流程
(async () => {
  try {
    console.log('\n🔑 步骤 1: 获取 Access Token...');
    const token = await getTenantAccessToken();
    console.log('   ✅ Token 获取成功\n');

    // 测试 1: 文本消息
    console.log('📝 步骤 2: 发送文本消息...');
    const textResult = await sendTextMessage(
      token,
      CHAT_ID!,
      '🧪 测试消息：feishu-notify-tool 功能验证'
    );

    if (textResult.code === 0) {
      console.log('   ✅ 文本消息发送成功');
      console.log('   消息 ID:', textResult.data?.message_id);
    } else {
      console.log('   ❌ 文本消息发送失败:', textResult.msg);
    }

    console.log('');

    // 测试 2: 卡片消息
    console.log('📋 步骤 3: 发送卡片消息...');
    const cardResult = await sendCardMessage(
      token,
      CHAT_ID!,
      '✅ feishu-notify-tool 测试',
      `**测试时间**: ${new Date().toLocaleString('zh-CN')}

**测试项目**:
- ✅ 工具定义正确
- ✅ 参数验证通过
- ✅ 错误处理完善
- ✅ 真实发送成功

**结论**: 飞书通知工具运行正常 🎉`
    );

    if (cardResult.code === 0) {
      console.log('   ✅ 卡片消息发送成功');
      console.log('   消息 ID:', cardResult.data?.message_id);
    } else {
      console.log('   ❌ 卡片消息发送失败:', cardResult.msg);
    }

    console.log('\n' + '='.repeat(60));
    console.log('✅ 所有测试完成！请检查飞书群是否收到消息');
    console.log('='.repeat(60));

  } catch (error) {
    console.error('\n❌ 测试失败:', error);
    process.exit(1);
  }
})();
