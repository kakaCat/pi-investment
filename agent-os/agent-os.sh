#!/bin/bash
# Agent OS 管理脚本 - 避免多实例端口冲突

AGENT_OS_DIR="/Users/yunpeng/pi-investment/agent-os"
AGENT_OS_BIN="$AGENT_OS_DIR/bin/agent-os"
PID_FILE="$AGENT_OS_DIR/.agent-os.pid"
LOG_FILE="$AGENT_OS_DIR/logs/agent-os.log"

# 创建日志目录
mkdir -p "$AGENT_OS_DIR/logs"

# 检查是否已运行
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # 运行中
        else
            rm -f "$PID_FILE"  # 清理过期 PID 文件
            return 1
        fi
    fi
    return 1
}

# 启动
start() {
    if check_running; then
        echo "Agent OS 已经在运行中 (PID: $(cat $PID_FILE))"
        return 1
    fi
    
    # 确保端口没被占用
    if lsof -i :8080 > /dev/null 2>&1; then
        echo "错误: 端口 8080 已被占用"
        lsof -i :8080
        return 1
    fi
    
    echo "启动 Agent OS..."
    cd "$AGENT_OS_DIR"
    nohup "$AGENT_OS_BIN" serve > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    # 等待启动
    sleep 3
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ Agent OS 启动成功 (PID: $PID)"
        echo "   日志: $LOG_FILE"
        echo "   HTTP: http://localhost:8080"
        return 0
    else
        echo "❌ Agent OS 启动失败"
        cat "$LOG_FILE" | tail -20
        rm -f "$PID_FILE"
        return 1
    fi
}

# 停止
stop() {
    if ! check_running; then
        echo "Agent OS 未运行"
        # 强制清理端口占用
        PIDS=$(lsof -ti :8080,8081)
        if [ -n "$PIDS" ]; then
            echo "发现端口占用，强制清理..."
            kill -9 $PIDS 2>/dev/null
        fi
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    echo "停止 Agent OS (PID: $PID)..."
    kill "$PID" 2>/dev/null
    
    # 等待进程退出
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Agent OS 已停止"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    
    # 强制杀死
    echo "强制停止..."
    kill -9 "$PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "✅ Agent OS 已强制停止"
}

# 重启
restart() {
    stop
    sleep 2
    start
}

# 状态
status() {
    if check_running; then
        PID=$(cat "$PID_FILE")
        echo "✅ Agent OS 运行中"
        echo "   PID: $PID"
        echo "   内存: $(ps -o rss= -p $PID | awk '{print $1/1024 "MB"}')"
        echo "   运行时长: $(ps -o etime= -p $PID | xargs)"
        
        # 检查端口
        if lsof -i :8080 -sTCP:LISTEN > /dev/null 2>&1; then
            echo "   HTTP: ✅ http://localhost:8080"
        else
            echo "   HTTP: ❌ 端口未监听"
        fi
        
        # 最近日志
        echo ""
        echo "最近日志:"
        tail -10 "$LOG_FILE"
    else
        echo "❌ Agent OS 未运行"
        
        # 检查是否有进程占用端口
        if lsof -i :8080 > /dev/null 2>&1; then
            echo ""
            echo "⚠️  端口 8080 被其他进程占用:"
            lsof -i :8080
        fi
    fi
}

# 日志
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "日志文件不存在: $LOG_FILE"
    fi
}

# 主命令
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "命令:"
        echo "  start    - 启动 Agent OS"
        echo "  stop     - 停止 Agent OS"
        echo "  restart  - 重启 Agent OS"
        echo "  status   - 查看状态"
        echo "  logs     - 查看实时日志"
        exit 1
        ;;
esac
