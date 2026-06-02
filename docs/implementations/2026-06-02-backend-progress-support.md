# 后端进度支持实施方案

**日期**: 2026-06-02  
**任务**: 为批量操作工具添加 WebSocket 进度推送

---

## 一、实施方案概述

### 方案选择：WebSocket 实时推送

**理由**：
- quantsys-v2 已有 WebSocket 服务器（端口 5003）
- 实时性最好，无轮询开销
- 代码复用性高

**架构**：
```
前端工具 (TypeScript)
    ↓ HTTP POST /api/pools/123/validate
后端 API (Flask)
    ↓ 调用 PoolValidationService
Service
    ↓ 推送进度到 WebSocket
    ↙           ↘
WebSocket Server → 前端监听
```

---

## 二、已实现组件

### 2.1 ProgressEmitter 核心类

**文件**: `quantsys-v2/runtime/progress_emitter.py`

**功能**：
- 记录任务进度（current/total）
- 推送进度到 WebSocket
- 自动计算百分比
- 记录日志

**核心方法**：
```python
class ProgressEmitter:
    def update(increment=1, message="")    # 更新进度
    def complete(message="")               # 标记完成
    def error(error_message)               # 标记失败
```

**使用示例**：
```python
emitter = ProgressEmitter(
    task_id="pool_123_validate",
    total=50,
    emit_func=socketio.emit
)

emitter.update(1, "正在加载股票池")
emitter.update(5, "正在执行回测...")
emitter.complete("验证完成")
```

### 2.2 服务层集成

**文件**: `quantsys-v2/services/pool_validation_service.py`

**修改内容**：
1. 导入 `ProgressEmitter`
2. `validate_pool` 添加 `progress_emitter` 参数
3. 在关键步骤调用 `emitter.update()`

**进度节点**：
```python
emitter.update(1, "正在加载股票池 #123")        # 步骤 1
emitter.update(1, "正在加载策略列表")            # 步骤 2
emitter.update(1, "开始批量回测：150 个任务")   # 步骤 3
emitter.update(0, "正在执行 150 个回测任务...")  # 步骤 4
emitter.update(1, "正在汇总策略结果")            # 步骤 5
emitter.complete("验证完成")                     # 完成
```

---

## 三、剩余实施步骤

### 步骤 1: 修改 API 路由（后端）

**文件**: `quantsys-v2/api/routes/pools.py`

**需要修改**：
```python
@pools_bp.route('/api/pools/<int:pool_id>/validate', methods=['POST'])
def validate_pool(pool_id):
    _, val_svc = _get_services()
    data = request.get_json() or {}
    
    # 生成任务ID
    task_id = f"pool_{pool_id}_validate_{int(time.time())}"
    
    # 创建进度发射器（需要 socketio 实例）
    from api.server_websocket import socketio
    emitter = ProgressEmitter(
        task_id=task_id,
        total=5,  # 总步骤数
        emit_func=lambda event, data: socketio.emit(event, data, broadcast=True)
    )
    
    try:
        result = val_svc.validate_pool(
            pool_id=pool_id,
            strategy_ids=data.get('strategyIds') or data.get('strategy_ids'),
            start_date=data.get('startDate') or data.get('start_date'),
            end_date=data.get('endDate') or data.get('end_date'),
            progress_emitter=emitter  # 传入发射器
        )
        
        emitter.complete("验证完成")
        
        # 返回时包含 task_id
        return jsonify({
            'success': True, 
            'data': result,
            'task_id': task_id
        })
    except Exception as e:
        emitter.error(str(e))
        raise
```

### 步骤 2: 前端集成（TypeScript）

**文件**: `src/infrastructure/tools/pool/pool-validate-tool.ts`

**需要修改**：

```typescript
import { io, Socket } from 'socket.io-client';
import { formatProgressOutput } from '../shared/output-formatters.js';

// 全局 WebSocket 连接（复用）
let wsConnection: Socket | null = null;

function getWebSocket(): Socket {
  if (!wsConnection) {
    wsConnection = io('http://127.0.0.1:5003', {
      transports: ['websocket'],
      autoConnect: true
    });
  }
  return wsConnection;
}

export const poolValidateTool: ToolDefinition = {
  // ... 现有定义 ...
  
  execute: async (_toolCallId: string, rawParams: any) => {
    const { pool_id, strategy_ids, start_date, end_date } = rawParams;
    
    // 连接 WebSocket
    const ws = getWebSocket();
    
    // 监听进度事件
    ws.on('progress', (data) => {
      if (data.completed) {
        console.log(`✅ ${data.message}`);
      } else if (data.error) {
        console.error(`❌ ${data.message}`);
      } else {
        // 显示进度条
        const progress = formatProgressOutput(
          data.current,
          data.total,
          data.message
        );
        console.log(progress);
      }
    });
    
    try {
      // 调用 API
      const resp = await validatePool(pool_id, {
        strategy_ids,
        start_date,
        end_date,
      });
      
      // 格式化输出（现有逻辑）
      const data = resp?.data ?? resp;
      const text = _formatValidation(data);
      
      return { 
        content: [{ type: "text" as const, text }], 
        details: undefined 
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `❌ 验证失败: ${error instanceof Error ? error.message : String(error)}`,
        }],
        details: undefined,
      };
    } finally {
      // 清理监听器
      ws.off('progress');
    }
  },
};
```

### 步骤 3: 安装依赖（前端）

```bash
cd /Users/mac/Documents/ai/pi-investment
npm install socket.io-client
```

### 步骤 4: 测试验证

**测试步骤**：

1. **启动后端服务**：
```bash
cd quantsys-v2
python start_all.py  # REST API (5001) + WebSocket (5003)
```

2. **测试进度推送**（Python 脚本）：
```python
import socketio
import time

# 连接 WebSocket
sio = socketio.Client()
sio.connect('http://127.0.0.1:5003')

@sio.on('progress')
def on_progress(data):
    print(f"进度: {data['current']}/{data['total']} - {data['message']}")

# 触发验证（使用 HTTP 客户端或工具）
# ...

time.sleep(30)  # 等待完成
sio.disconnect()
```

3. **测试前端工具**：
```typescript
// 在 Agent 中调用
pool_validate({ pool_id: 1, strategy_ids: [53, 54] })
```

**预期输出**：
```
进度：[█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 20% (1/5)
正在加载股票池 #1

进度：[████░░░░░░░░░░░░░░░░░░░░░░░░░░] 40% (2/5)
正在加载策略列表

进度：[████████░░░░░░░░░░░░░░░░░░░░░░] 60% (3/5)
开始批量回测：150 个任务

进度：[████████████░░░░░░░░░░░░░░░░░░] 80% (4/5)
正在汇总策略结果

进度：[█████████████████████████████░] 100% (5/5)
✅ 验证完成
```

---

## 四、进度节点设计

### pool_validate 进度节点

| 步骤 | 进度 | 消息 | 预计耗时 |
|------|------|------|----------|
| 1 | 20% | 正在加载股票池 #123 | < 0.5s |
| 2 | 40% | 正在加载策略列表 | < 1s |
| 3 | 60% | 开始批量回测：150 个任务 | < 1s |
| 4 | 80% | 正在执行 150 个回测任务... | 30-180s |
| 5 | 100% | 正在汇总策略结果 | < 2s |

**总耗时**：30-180秒（取决于任务数量）

### strategy_batch_validate 进度节点

类似设计，分为：
1. 加载策略列表
2. 生成回测任务
3. 执行批量回测
4. 计算综合评分
5. 保存结果

---

## 五、技术细节

### 5.1 WebSocket 消息格式

**进度消息**：
```json
{
  "task_id": "pool_123_validate_1654321234",
  "current": 3,
  "total": 5,
  "percentage": 60.0,
  "message": "开始批量回测：150 个任务",
  "timestamp": "2026-06-02T10:30:00.000Z"
}
```

**完成消息**：
```json
{
  "task_id": "pool_123_validate_1654321234",
  "current": 5,
  "total": 5,
  "percentage": 100,
  "message": "验证完成",
  "elapsed_seconds": 45.2,
  "completed": true,
  "timestamp": "2026-06-02T10:30:45.200Z"
}
```

**错误消息**：
```json
{
  "task_id": "pool_123_validate_1654321234",
  "current": 3,
  "total": 5,
  "percentage": 60.0,
  "message": "回测API调用失败",
  "error": true,
  "elapsed_seconds": 15.5,
  "timestamp": "2026-06-02T10:30:15.500Z"
}
```

### 5.2 前端进度条样式

使用 `formatProgressOutput`：
```typescript
formatProgressOutput(
  current: 3,
  total: 5,
  message: "正在执行回测..."
)

// 输出：
// 进度：[████████████████░░░░░░░░░░░░░░] 60% (3/5)
// 正在执行回测...
```

---

## 六、性能影响评估

### 6.1 WebSocket 开销

| 指标 | 影响 |
|------|------|
| 连接建立 | ~50-100ms（一次性） |
| 单次消息 | ~1-5ms（可忽略） |
| 内存开销 | ~1KB/连接 |

**评估**：对批量操作（30-180秒）的性能影响 < 0.1%

### 6.2 进度推送频率

**当前设计**：
- 固定节点推送（5次）
- 不按时间间隔推送

**优点**：
- 推送次数少（5次 vs 可能数百次）
- 不增加网络负担
- 足够的进度反馈

**如果需要更细粒度**：
- 可在回测循环中每10%推送一次
- 或每10秒推送一次当前状态

---

## 七、后续优化建议

### 7.1 进度粒度增强

**当前**：5个固定节点

**增强方案**：
```python
# 在回测循环中推送
for i, job in enumerate(jobs):
    result = backtest_one(job)
    
    # 每10%推送一次
    if (i + 1) % (len(jobs) // 10) == 0:
        emitter.update(0, f"已完成 {i+1}/{len(jobs)} 个回测")
```

**收益**：
- 更细粒度的进度反馈
- 更准确的剩余时间估算

**成本**：
- 更多的 WebSocket 消息
- 稍微增加网络开销

### 7.2 剩余时间估算

```python
class ProgressEmitter:
    def estimate_remaining(self) -> float:
        """估算剩余时间（秒）"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.current == 0:
            return 0
        
        avg_time_per_step = elapsed / self.current
        remaining_steps = self.total - self.current
        return avg_time_per_step * remaining_steps
```

**使用**：
```python
remaining = emitter.estimate_remaining()
emitter.update(1, f"预计剩余 {int(remaining)} 秒")
```

### 7.3 取消任务支持

**需求**：允许用户取消长时间运行的任务

**实现**：
```python
# 前端发送取消请求
ws.emit('cancel_task', { task_id: '...' })

# 后端检查取消标志
if should_cancel(task_id):
    emitter.error("任务已取消")
    break
```

---

## 八、总结

### 已完成

1. ✅ ProgressEmitter 核心类（145行）
2. ✅ 服务层集成（5个进度节点）
3. ✅ 实施方案文档

### 待完成（预计 0.5-1天）

1. ⏳ 修改 API 路由（集成 WebSocket）
2. ⏳ 前端工具集成（监听进度）
3. ⏳ 安装前端依赖（socket.io-client）
4. ⏳ 测试验证

### 下一步

执行"待完成"的4个步骤，完整实现进度推送功能。

需要我继续实施剩余步骤吗？

---

**文档位置**: `docs/implementations/2026-06-02-backend-progress-support.md`
