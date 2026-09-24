# Git Worktree 工作流规范

## 一、为什么用 Worktree？

在 PI Investment 项目中，多个 Claude 会话或人工可能同时工作：
- ✅ **隔离**：每个任务在独立目录，避免冲突
- ✅ **历史**：每次提交都保留，便于回溯
- ✅ **验证**：合并前可以完整测试
- ✅ **安全**：主分支始终干净，随时可回退

## 二、标准操作流程

### 阶段 1：开始新任务（创建 Worktree）

``ash
# 1. 确认当前在主工作区
cd /Users/yunpeng/pi-investment/agent-dh

# 2. 创建 worktree（自动创建分支）
git worktree add .claude/worktrees/<任务名> -b feat/<任务名>

# 例如：实现需求 REQ-123
git worktree add .claude/worktrees/req-123 -b feat/req-123

# 3. 进入 worktree 开始工作
cd .claude/worktrees/req-123
```

**命名规范**：
- `feat/<功能名>` - 新功能
- `fix/<问题名>` - 修复 bug
- `refactor/<重构名>` - 重构代码
- `docs/<文档名>` - 文档更新

### 阶段 2：开发过程（定期提交）

```bash
# 在 worktree 目录内工作
cd .claude/worktrees/req-123

# 修改代码...

# 定期提交（保留历史）
git add <修改的文件>
git commit -m "feat(pmboard): 实现 XXX 功能"

# 继续开发...
git add <更多文件>
git commit -m "feat(pmboard): 完善 YYY 逻辑"

# 可以随时查看历史
git log --oneline
```

**提交信息规范**（Conventional Commits）：
- `feat(scope): 描述` - 新功能
- `fix(scope): 描述` - 修复
- `refactor(scope): 描述` - 重构
- `docs(scope): 描述` - 文档
- `test(scope): 描述` - 测试

### 阶段 3：完成开发（验证）

```bash
# 在 worktree 内验证
cd .claude/worktrees/req-123

# 运行测试
pnpm test

# 构建检查
pnpm build

# 启动服务验证
cd ../../../  # 回到 agent-dh 根目录
./scripts/start.sh --port 13081  # 使用临时端口测试

# 验证通过后，最后一次提交
cd .claude/worktrees/req-123
git add .
git commit -m "feat(pmboard): 完成 REQ-123 实现"
```

### 阶段 4：合并到 Main（完成任务）

```bash
# 1. 回到主工作区
cd /Users/yunpeng/pi-investment/agent-dh

# 2. 确保 main 是最新的
git checkout main
git pull origin main

# 3. 合并 worktree 分支（保留历史）
git merge --no-ff feat/req-123 -m "Merge feat/req-123: 完成 REQ-123"

# 或者使用 rebase（线性历史）
git merge --ff-only feat/req-123

# 4. 推送到远程
git push origin main

# 5. 删除 worktree 和分支
git worktree remove .claude/worktrees/req-123
git branch -d feat/req-123
```

### 阶段 5：清理（可选）

```bash
# 查看所有 worktrees
git worktree list

# 删除已完成的 worktree
git worktree remove .claude/worktrees/<任务名>

# 如果 worktree 目录已手动删除，用 prune 清理
git worktree prune
```

## 三、最佳实践

### 3.1 目录结构

```
agent-dh/
├── .claude/
│   └── worktrees/
│       ├── req-123/      # 需求 123 的独立工作区
│       ├── fix-bug-456/  # Bug 修复的独立工作区
│       └── refactor-789/ # 重构任务的独立工作区
├── packages/             # 主工作区的代码
├── docs/
└── scripts/
```

### 3.2 多人协作规则

1. **每个任务一个 worktree**：避免在 main 上直接修改
2. **频繁提交**：小步快跑，便于回滚
3. **定期同步 main**：
   ```bash
   cd .claude/worktrees/req-123
   git fetch origin
   git rebase origin/main  # 或 git merge origin/main
   ```
4. **合并前自查**：
   - 所有测试通过
   - 没有遗留的 console.log / debugger
   - 代码符合规范

### 3.3 紧急情况处理

**场景 1：需要切换到另一个任务**
```bash
# 当前在 worktree A，需要切换到 worktree B
cd .claude/worktrees/task-b
# 两个 worktree 互不影响
```

**场景 2：Worktree 创建失败（分支已存在）**
```bash
# 删除旧分支后重建
git branch -D feat/old-branch
git worktree add .claude/worktrees/new-task -b feat/new-branch
```

**场景 3：Main 分支有冲突**
```bash
cd .claude/worktrees/req-123
git fetch origin
git rebase origin/main
# 解决冲突
git add <冲突文件>
git rebase --continue
```

## 四、当前状态处理

### 你现在的情况

```bash
# 当前在 main 分支，有大量未提交修改
git status --short
# M 代表已修改但未提交的文件
```

### 建议操作

#### 选项 A：把当前修改移到 worktree（推荐）

```bash
# 1. 暂存当前修改
git stash push -m "WIP: 当前工作进度"

# 2. 创建新 worktree
git worktree add .claude/worktrees/current-work -b feat/current-work

# 3. 在 worktree 中恢复修改
cd .claude/worktrees/current-work
git stash pop

# 4. 提交修改
git add .
git commit -m "feat: 当前工作的第一次提交"

# 5. 继续在 worktree 中开发...
```

#### 选项 B：直接在 main 上提交（不推荐）

```bash
# 仅用于紧急修复或文档更新
git add .
git commit -m "fix: 紧急修复"
git push origin main
```

## 五、自动化脚本（可选）

### 创建 worktree 快捷脚本

```bash
# scripts/new-worktree.sh
#!/bin/bash
TASK_NAME=${1:-$(date +%Y%m%d-%H%M%S)}
WORKTREE_PATH=".claude/worktrees/$TASK_NAME"
BRANCH_NAME="feat/$TASK_NAME"

git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
echo "✅ Worktree created: $WORKTREE_PATH"
echo "📝 Branch: $BRANCH_NAME"
echo "🚀 Run: cd $WORKTREE_PATH"
```

### 合并并清理脚本

```bash
# scripts/merge-worktree.sh
#!/bin/bash
BRANCH_NAME=$1
WORKTREE_PATH=$2

if [ -z "$BRANCH_NAME" ]; then
  echo "Usage: ./scripts/merge-worktree.sh <branch-name> <worktree-path>"
  exit 1
fi

# 回到 main
git checkout main
git pull origin main

# 合并
git merge --no-ff "$BRANCH_NAME" -m "Merge $BRANCH_NAME"

# 推送
git push origin main

# 清理
git worktree remove "$WORKTREE_PATH"
git branch -d "$BRANCH_NAME"

echo "✅ Merged and cleaned: $BRANCH_NAME"
```

## 六、检查清单

**开始新任务前：**
- [ ] 确认在主工作区（`git worktree list`）
- [ ] Main 分支是最新的（`git pull`）
- [ ] 没有未提交的修改（`git status`）

**提交前：**
- [ ] 代码已测试通过
- [ ] 提交信息清晰
- [ ] 没有敏感信息（API key、密码）

**合并前：**
- [ ] 所有测试通过
- [ ] 代码已 review
- [ ] 与 main 同步（`git rebase origin/main`）
- [ ] 冲突已解决

**合并后：**
- [ ] Worktree 已删除
- [ ] 分支已删除
- [ ] Main 已推送到远程

---

**最后更新**: 2026-09-23
**维护者**: PI Investment Team
