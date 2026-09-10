# Agent-DH 频繁重启问题 - 根本解决方案

## 问题现象

agent-dh 每 2-4 小时自动重启一次，日志显示：
```
FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
Mark-Compact 4047.8 (4141.2) -> 4041.3 (4143.6) MB
```

## 根本原因

1. **内存泄漏**：多窗口共享单进程，会话历史持续积累
2. **堆上限过低**：Node.js 默认 4144MB，无法支撑多窗口长期运行
3. **依赖版本冲突**：`@deepseek-ai/dsh-llm` 版本不兼容

## 解决方案

### 方案 A：提升堆上限（临时治标，推荐）

修改 `agent-dh/start.sh`，设置 16GB 堆上限：

```bash
# 添加在启动命令前
DSH_MAX_OLD_SPACE="${DSH_MAX_OLD_SPACE:-16384}"
export NODE_OPTIONS="--max-old-space-size=${DSH_MAX_OLD_SPACE} --import tsx/esm"
```

**优点**：简单快速，立即生效
**缺点**：治标不治本，内存仍会持续增长

### 方案 B：定期清理会话（治本）

创建定时任务，每天清理旧会话：

```bash
#!/bin/bash
# 清理 7 天前的会话
find ~/.dsh/sessions -type f -mtime +7 -delete
find ~/.dsh-agent-dh/sessions -type f -mtime +7 -delete
```

### 方案 C：定期重启（兜底方案）

使用 cron 或 launchd 每天凌晨自动重启一次：

```bash
# crontab -e
0 3 * * * cd /Users/yunpeng/pi-investment/agent-dh && pkill -f 'dsh.*investment' && sleep 5 && bash start.sh > /tmp/agent-dh.log 2>&1 &
```

### 方案 D：升级依赖（根治，但风险较高）

更新 `package.json` 中的 DSH 依赖到最新版本：

```json
"@deepseek-ai/dsh-agent": "^0.1.2-alpha.4",
"@deepseek-ai/dsh-llm": "^0.1.2-alpha.4",
...
```

**风险**：可能引入新的不兼容问题

## 推荐执行步骤

### 立即修复（5分钟）

1. **停止当前进程**：
   ```bash
   pkill -f 'dsh.*investment'
   ```

2. **修改启动脚本**（已完成）：
   - 文件：`/Users/yunpeng/pi-investment/agent-dh/start.sh`
   - 已添加 16GB 堆上限配置

3. **清理历史会话**：
   ```bash
   # 备份
   cp -r ~/.dsh/sessions ~/.dsh/sessions-backup-$(date +%Y%m%d)

   # 清理 3 天前的
   find ~/.dsh/sessions -type f -mtime +3 -delete
   ```

4. **重新启动**：
   ```bash
   cd /Users/yunpeng/pi-investment/agent-dh
   bash start.sh > /tmp/agent-dh.log 2>&1 &
   ```

5. **验证**：
   ```bash
   # 检查进程
   ps aux | grep 'dsh.*investment'

   # 检查内存
   ps -o pid,rss,vsz,comm $(pgrep -f 'dsh.*investment')

   # 监控堆使用
   # （需要在 agent-dh 内执行）
   node -e "console.log(require('v8').getHeapStatistics())"
   ```

### 长期监控（建议）

1. **添加内存监控脚本**：
   ```bash
   #!/bin/bash
   # monitor-agent-dh.sh
   while true; do
     PID=$(pgrep -f 'dsh.*investment')
     if [ -n "$PID" ]; then
       RSS=$(ps -o rss= -p $PID | awk '{print $1/1024}')
       echo "$(date): PID=$PID, RSS=${RSS}MB"
       
       # 如果超过 14GB，主动重启
       if (( $(echo "$RSS > 14336" | bc -l) )); then
         echo "Memory limit reached, restarting..."
         pkill -f 'dsh.*investment'
         sleep 5
         cd /Users/yunpeng/pi-investment/agent-dh && bash start.sh &
       fi
     fi
     sleep 300  # 每 5 分钟检查一次
   done
   ```

2. **设置每日自动清理**（launchd）：
   ```xml
   <!-- ~/Library/LaunchAgents/com.pi-investment.cleanup-sessions.plist -->
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.pi-investment.cleanup-sessions</string>
       <key>ProgramArguments</key>
       <array>
           <string>/bin/bash</string>
           <string>-c</string>
           <string>find ~/.dsh/sessions -type f -mtime +7 -delete</string>
       </array>
       <key>StartCalendarInterval</key>
       <dict>
           <key>Hour</key>
           <integer>3</integer>
           <key>Minute</key>
           <integer>0</integer>
       </dict>
   </dict>
   </plist>
   ```

   激活：
   ```bash
   launchctl load ~/Library/LaunchAgents/com.pi-investment.cleanup-sessions.plist
   ```

## 效果预期

- **修复前**：2-4 小时重启一次
- **修复后**：至少 24 小时稳定运行
- **最佳情况**：配合定期清理，可持续运行数周

## 监控指标

正常运行状态：
- 启动内存：500-800MB
- 稳态内存：2-4GB
- 增长速度：< 100MB/小时（清理后）
- 堆使用率：< 80%

异常信号：
- 内存增长 > 200MB/小时
- RSS 超过 12GB
- 频繁 GC（Mark-Compact）
- 日志中出现 "heap out of memory"

## 故障排查

如果修复后仍然重启：

1. **检查堆上限是否生效**：
   ```bash
   ps aux | grep 'dsh.*investment'
   # 查看进程的 NODE_OPTIONS 环境变量
   ```

2. **检查是否是其他原因重启**：
   ```bash
   # 查看重启日志
   ls -lt ~/.dsh-agent-dh/profiles/investment/state/restart-*.log | head -5
   
   # 查看错误日志
   tail -100 /tmp/agent-dh.log | grep -i "error\|fatal"
   ```

3. **检查依赖冲突**：
   ```bash
   cd /Users/yunpeng/pi-investment/agent-dh
   pnpm list @deepseek-ai/dsh-llm
   ```

## 参考

- 修复提交：`f3d9a8bd` (2026-09-11)
- 相关提交：`57b0f00b` (lifecycle 修复)
- OOM 日志：`~/.dsh-agent-dh/profiles/investment/state/restart-1789051901380.log`

## 最后更新

2026-09-11 - 初版
