# Codex 异步任务系统

## 工作流程

```
1. Claude 提交异步任务
   ↓
2. 写入 bridge/codex/pending/task_xxx.json
   ↓
3. Bridge 检测并执行
   ↓
4. 完成后写入 bridge/codex/completed/task_xxx.json
   ↓
5. 同时写入 bridge/codex/notifications/task_xxx.txt
   ↓
6. Claude Hook 监听到通知
   ↓
7. 自动读取结果并展示
```

## 使用方法

### 1. 提交异步任务

```typescript
mcp__codex__task_async({
  prompt: "测试所有量化模块并生成报告",
  workdir: "/Users/mac/Documents/ai/pi-investment"
})

// 返回: ✅ 任务已提交，ID: task_1234567890
```

### 2. 检查结果

```typescript
// 检查特定任务
mcp__codex__check_results({ task_id: "task_1234567890" })

// 列出所有完成的任务
mcp__codex__check_results({})
```

### 3. 自动通知（Hook）

当任务完成时，Hook 自动触发，Claude 收到通知。

## 目录结构

```
bridge/codex/
├── pending/        # 待执行任务
├── completed/      # 已完成任务
└── notifications/  # 通知文件（触发Hook）
```
