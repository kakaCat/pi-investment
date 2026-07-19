#!/bin/bash
# 系统启动时自动启动调度器守护进程

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 设置调度器守护进程开机自启动"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 方案1: 使用 launchd (macOS)
PLIST_FILE="$HOME/Library/LaunchAgents/com.pi-investment.scheduler.plist"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pi-investment.scheduler</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/scripts/start-daemon.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
    </dict>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/.pi-invest/logs/scheduler-daemon.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/.pi-invest/logs/scheduler-daemon.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.nvm/versions/node/v25.1.0/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ 已创建 launchd 配置文件: $PLIST_FILE"
echo ""

# 加载配置
launchctl unload "$PLIST_FILE" 2>/dev/null
launchctl load "$PLIST_FILE"

echo "✅ 已加载到 launchd"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 管理命令:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "查看状态:"
echo "  launchctl list | grep pi-investment"
echo ""
echo "停止服务:"
echo "  launchctl unload $PLIST_FILE"
echo ""
echo "启动服务:"
echo "  launchctl load $PLIST_FILE"
echo ""
echo "查看日志:"
echo "  tail -f $PROJECT_DIR/.pi-invest/logs/scheduler-daemon.log"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 设置完成！调度器将在系统启动时自动运行"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
