# 获取飞书 Webhook URL 操作指南

## 步骤 1: 打开飞书群聊

1. 打开飞书应用
2. 进入你想接收通知的群聊（或创建一个新的测试群）

## 步骤 2: 添加自定义机器人

1. 点击群聊右上角的 **设置图标** ⚙️
2. 选择 **群机器人**
3. 点击 **添加机器人**
4. 选择 **自定义机器人**

## 步骤 3: 配置机器人

1. **机器人名称**: 填写一个名字，例如 "PI Investment 通知"
2. **机器人描述**: 可选，例如 "投资顾问系统通知"
3. 点击 **下一步**

## 步骤 4: 获取 Webhook URL

添加成功后，会显示一个 Webhook URL，格式如下：

```
https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**复制这个 URL！** 📋

## 步骤 5: 配置到项目

打开文件：`agent-ts/.env`

添加一行：

```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你复制的webhook地址
```

保存文件。

## 步骤 6: 测试发送

运行测试脚本：

```bash
cd agent-ts
npx tsx src/scripts/test-feishu-integration.ts
```

如果配置正确，你会在飞书群收到测试消息！

---

## 📸 界面示意

```
飞书群聊界面
├── 右上角 ⚙️ 设置
│   └── 群机器人
│       ├── 添加机器人
│       │   ├── 自定义机器人 ← 选这个
│       │   ├── 企业应用机器人
│       │   └── ...
│       └── 已添加的机器人
│
└── 配置机器人
    ├── 名称: PI Investment 通知
    ├── 描述: (可选)
    └── [添加] → 获取 Webhook URL
```

---

## ⚠️ 注意事项

1. **保密**: Webhook URL 包含认证信息，不要泄露
2. **限制**: 每个机器人有消息频率限制
3. **有效期**: URL 长期有效，除非删除机器人

---

## ✅ 验证方式

配置完成后，可以通过以下方式验证：

### 方法 1: 运行测试脚本
```bash
npx tsx src/scripts/test-feishu-integration.ts
```

### 方法 2: 使用 curl 测试
```bash
curl -X POST "你的webhook_url" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "text",
    "content": {
      "text": "测试消息"
    }
  }'
```

如果收到消息，说明配置成功！
