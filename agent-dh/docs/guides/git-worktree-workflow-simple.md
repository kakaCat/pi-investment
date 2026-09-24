# Git Worktree 工作流（简化版）

## 核心流程

### 1. 立项时创建 Worktree

```bash
cd /Users/yunpeng/pi-investment/agent-dh

# 创建 worktree
git worktree add .claude/worktrees/<任务名> -b feat/<任务名>

# 进入工作
cd .claude/worktrees/<任务名>
```

### 2. 实施过程中随时提交

```bash
# 完成一个功能点就 commit 一次
git add .
git commit -m "feat: 完成 XXX"

# 继续开发...
git add .
git commit -m "feat: 完成 YYY"
```

### 3. 实施完成后合并到 main

```bash
# 回到主工作区
cd /Users/yunpeng/pi-investment/agent-dh

# 切换到 main
git checkout main

# 合并 worktree 分支
git merge --no-ff feat/<任务名> -m "Merge feat/<任务名>"

# 推送
git push origin main

# 删除 worktree 和分支
git worktree remove .claude/worktrees/<任务名>
git branch -d feat/<任务名>
```

## 快捷命令

```bash
# 新建任务
./scripts/new-worktree.sh <任务名>

# 查看所有 worktrees
git worktree list

# 清理残留
git worktree prune
```

---

就这么简单：**立项建 worktree → 开发中随时 commit → 完成后合并删除**
