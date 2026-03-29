# Codex 异步任务目录

## 目录结构

```
bridge/codex/
├── pending/       # 待处理任务
│   └── task_xxx.json
└── completed/     # 已完成任务
    └── task_xxx.json
```

## 工作流程

1. Claude 调用 `task_async` → 生成 `pending/task_xxx.json`
2. Bridge 检测到新任务 → 执行
3. 完成后移动到 `completed/task_xxx.json`
4. Claude 检查 `completed/` 获取结果
