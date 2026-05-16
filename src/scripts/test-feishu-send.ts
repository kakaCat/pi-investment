import * as lark from "@larksuiteoapi/node-sdk";
import "dotenv/config";

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
const CHAT_ID = process.env.FEISHU_CHAT_ID || process.argv[2];

if (!APP_ID || !APP_SECRET) {
  console.error("❌ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET");
  process.exit(1);
}

if (!CHAT_ID) {
  console.error("❌ 缺少 FEISHU_CHAT_ID");
  console.error("\n使用方法：");
  console.error("  1. 在 .env 中设置 FEISHU_CHAT_ID=<your_chat_id>");
  console.error("  2. 或者运行: npx tsx src/scripts/test-feishu-send.ts <chat_id>");
  console.error("\n如何获取 chat_id：");
  console.error("  - 在飞书群聊中发送消息给机器人");
  console.error("  - 查看服务器日志中的 chat_id");
  process.exit(1);
}

const client = new lark.Client({
  appId: APP_ID,
  appSecret: APP_SECRET,
  appType: lark.AppType.SelfBuild,
  domain: lark.Domain.Feishu,
});

async function sendMessage(chatId: string, text: string) {
  const card = {
    config: { wide_screen_mode: true },
    elements: [{ tag: "markdown", content: text }],
    header: {
      template: "blue",
      title: { tag: "plain_text", content: "Pi Investment - 测试消息" }
    }
  };

  await client.im.message.create({
    params: { receive_id_type: "chat_id" },
    data: {
      receive_id: chatId,
      msg_type: "interactive",
      content: JSON.stringify(card),
    },
  });
}

// 发送测试消息
sendMessage(CHAT_ID, `✅ **Codex 配置问题已修复**

**问题**：Codex 账户余额不足（402 Payment Required）

**解决方案**：
- 已添加配置开关，默认禁用自动代码生成
- 进化系统仍可正常运行，生成优化建议
- 需要手动实现建议的工具

**配置位置**：\`src/config/config.ts\`
\`\`\`typescript
export const evolutionConfig = {
  enableCodeGeneration: false,  // 默认关闭
};
\`\`\`

**详细文档**：\`docs/codex-setup-guide.md\`

发送时间：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`)
  .then(() => {
    console.log("✅ 消息发送成功");
    process.exit(0);
  })
  .catch((error) => {
    console.error("❌ 消息发送失败:", error);
    process.exit(1);
  });
