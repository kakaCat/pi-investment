# DSH Session Repair Tools

## 问题描述

DSH Web GUI 遇到会话持久化损坏错误：

```
SessionPersistenceCorruptionError: stored session "session-xxx" failed validation: 
Error: session event at seq XXX lacks an identified message
```

这个错误表示会话文件中的某个事件缺少必需的消息标识（message.id）。

## 根本原因

在会话持久化过程中，某些消息事件（user/message、assistant/message、tool/result）的消息对象缺少 `id` 字段，导致：

1. 会话无法加载
2. 历史记录丢失
3. 无法恢复之前的会话上下文

## 修复工具

### 1. 会话健康检查工具 (session-health-check.mjs)

扫描所有会话文件，检测潜在的损坏问题。

**用法：**

```bash
# 检查所有会话
node session-health-check.mjs ~/.dsh/sessions

# 详细输出（包括健康的会话）
node session-health-check.mjs --verbose ~/.dsh/sessions

# 查看帮助
node session-health-check.mjs --help
```

**输出示例：**

```
Found 42 session file(s)

================================================================================
Health Check Summary
================================================================================

Total sessions: 42
  ✓ Healthy: 40
  ✗ Unhealthy: 2

Unhealthy Sessions:

Session: session-11b1926b-246b-4f50-8557-a2a056919922
  Path: /Users/xxx/.dsh/sessions/.../session.jsonl.zstd
  Events: 537
  Issues: 1
    - Seq 536: missing-message-id (assistant/message)
```

### 2. 会话修复工具 (session-repair.mjs)

修复检测到的会话文件问题。

**用法：**

```bash
# 预览修复（不实际修改文件）
node session-repair.mjs --dry-run /path/to/session.jsonl.zstd

# 执行修复
node session-repair.mjs /path/to/session.jsonl.zstd

# 查看帮助
node session-repair.mjs --help
```

**安全特性：**

- 修复前自动备份原文件（.backup-timestamp 后缀）
- 支持 dry-run 模式预览修复内容
- 为缺失的 message.id 生成唯一标识符

**修复过程：**

1. 读取并解压会话文件
2. 逐行解析 JSONL 格式
3. 检测缺少 message.id 的事件
4. 为这些事件生成 `repaired-msg-{seq}-{timestamp}` 格式的 ID
5. 备份原文件
6. 写入修复后的会话

## 快速修复流程

```bash
# 1. 进入项目目录
cd /Users/yunpeng/pi-investment/agent-dh

# 2. 检查所有会话
node session-health-check.mjs ~/.dsh/sessions

# 3. 如果发现问题会话，复制其路径
# 4. 先预览修复
node session-repair.mjs --dry-run <session-file-path>

# 5. 确认后执行修复
node session-repair.mjs <session-file-path>

# 6. 重新检查
node session-health-check.mjs ~/.dsh/sessions
```

## 注意事项

1. **修复后的会话可以加载，但修复的消息 ID 是生成的**，不是原始 ID
2. **备份文件会保留**，如果修复出现问题可以恢复：
   ```bash
   mv session.jsonl.zstd.backup-xxx session.jsonl.zstd
   ```
3. **建议在修复前停止 DSH 服务**，避免并发写入冲突
4. 如果问题会话是当前正在使用的会话，修复后需要刷新浏览器

## 预防措施

为了防止此类问题再次发生，建议：

1. 定期运行健康检查：
   ```bash
   # 添加到 crontab
   0 3 * * * cd /path/to/agent-dh && node session-health-check.mjs ~/.dsh/sessions
   ```

2. 监控 DSH 日志，关注会话持久化错误

3. 如果频繁出现此问题，可能需要：
   - 升级 DSH 版本
   - 检查系统资源（磁盘空间、内存）
   - 向 DeepSeek Harness 团队报告 bug

## 技术细节

### 会话文件格式

- 位置：`~/.dsh/sessions/{workspace}/{session-id}/session.jsonl.zstd`
- 格式：zstd 压缩的 JSONL（每行一个 JSON 对象）
- 每个事件包含：
  - `type`: 事件类型（如 'assistant/message'）
  - `data`: 事件数据
  - `seq`: 序列号

### 验证逻辑

DSH 在加载会话时会验证消息事件：

```javascript
// 来自 @deepseek-ai/dsh-session/lib/index.js
function assertMessageEventShape(event, subject) {
  const type = event["type"];
  if (type !== "user/message" && type !== "assistant/message" && type !== "tool/result") return;
  
  const data = event["data"];
  const message = type === "user/message" ? data : data?.["message"];
  
  // 这里会抛出 "lacks an identified message" 错误
  if (typeof message !== "object" || message === null || 
      typeof message["id"] !== "string" || message["id"] === "") {
    throw new Error(`${subject} lacks an identified message`);
  }
  // ...
}
```

## 故障排除

### 修复工具无法运行

```bash
# 确保 Node.js 版本 >= 18
node --version

# 检查文件权限
ls -la session-repair.mjs session-health-check.mjs

# 重新设置执行权限
chmod +x session-repair.mjs session-health-check.mjs
```

### 会话文件无法读取

```bash
# 检查文件是否存在
ls -la <session-file-path>

# 检查文件权限
stat <session-file-path>

# 如果是压缩格式问题，可能需要重新安装 zlib
npm install zlib
```

### 修复后仍然无法加载

可能的原因：
1. 会话文件还有其他类型的损坏（不只是缺少 message.id）
2. DSH 版本不兼容
3. 需要清除 DSH 缓存：`rm -rf ~/.dsh/cache/*`

## 联系支持

如果这些工具无法解决问题，请收集以下信息：

1. `session-health-check.mjs` 的输出
2. `session-repair.mjs --dry-run` 的输出
3. DSH 版本：`dsh --version`
4. 错误日志：`~/.dsh/profiles/investment/state/dsh-boot.log`

然后向 DeepSeek Harness 团队报告。
