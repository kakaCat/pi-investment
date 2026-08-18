# Claude Code Worktree 工具调研报告

**日期**: 2026-08-17  
**调研对象**: Claude Code 内置的 Worktree 工具  
**当前项目**: pi-investment

---

## 1. 概述

### 什么是 Git Worktree？

Git Worktree 允许你在同一个仓库中同时签出多个分支到不同的工作目录。每个 worktree 都有自己的工作区和索引，但共享同一个 `.git` 仓库。

### Claude Code 中的 Worktree 工具

Claude Code 提供了两个工具来管理 worktree：
1. `EnterWorktree` - 创建或进入 worktree
2. `ExitWorktree` - 退出并可选择删除 worktree

---

## 2. 当前项目 Worktree 使用情况

### 统计数据

```bash
总计: 33 个 worktrees
├── 主仓库: /Users/yunpeng/pi-investment (main)
└── 链接的 worktrees: 32 个
```

### Worktree 分布

**按分类统计**:
- **WP (Work Package)**: 10 个
  - wp-1-scheduler
  - wp-2-resource-manager
  - wp-3-memory
  - wp-4-agent-integration
  - wp-5-market-driver
  - wp-6-feishu-driver
  - wp-7-decision-system
  - wp-8-permissions-eventbus
  - wp14-skill-hub ⭐ (刚完成)

- **Feature (A/P/T 系列)**: 14 个
  - A0-T1, A0-T2, A0-T3
  - A1-T1, A1-T2
  - A2-T1, A3-T1
  - P0-T1, P0-T1-r2
  - P1-T1, P1-T3, P1-T4, P1-T5
  - batch3-integration

- **Memory (W 系列)**: 3 个
  - w1.1-memory-bridge
  - w1.2-memory-api
  - W1.4-memory-provider

- **Bug Fix/Maintenance**: 3 个
  - fix-assembly-a1
  - fix-recall-audit-stats
  - harden-shared-tools

- **Other**: 3 个
  - notification-system
  - t3-compaction
  - t3b-compaction-wiring
  - t5-cron-hardening

### 存储位置

```
/Users/yunpeng/pi-investment/
├── .git/                           # 主仓库
├── .claude/
│   └── worktrees/                  # 所有 worktrees
│       ├── A0-T1/
│       ├── A0-T2/
│       ├── wp14-skill-hub/         # ⭐ WP-14
│       └── ...
└── agent-os/
    └── .claude/
        └── worktrees/
            └── wp-3-memory/        # 子仓库的 worktree
```

---

## 3. EnterWorktree 工具详解

### 工具签名

```typescript
EnterWorktree(params?: {
  name?: string,      // worktree 名称（可选）
  path?: string       // 已存在的 worktree 路径（可选）
})
```

### 使用场景

#### 场景 1: 创建新 Worktree（自动命名）

```typescript
// 不传参数，自动生成随机名称
EnterWorktree()

// 结果:
// - 创建 .claude/worktrees/<random-name>/
// - 从 origin/main 创建新分支
// - 切换会话到新 worktree
```

**示例**:
```bash
# Claude 自动创建
/.claude/worktrees/skilled-dolphin-7x2q/
```

#### 场景 2: 创建命名 Worktree

```typescript
// 指定名称
EnterWorktree({ name: 'wp14-skill-hub' })

// 结果:
// - 创建 .claude/worktrees/wp14-skill-hub/
// - 创建分支 feat/wp14-skill-hub-integration
// - 切换会话到新 worktree
```

**WP-14 实际执行**:
```
Created worktree at:
  /Users/yunpeng/pi-investment/.claude/worktrees/wp14-skill-hub
  
Branch: feat/wp14-skill-hub-integration
Base: origin/main
```

#### 场景 3: 进入已存在的 Worktree

```typescript
// 切换到已存在的 worktree
EnterWorktree({ path: '.claude/worktrees/wp14-skill-hub' })

// 结果:
// - 不创建新目录
// - 切换会话到指定 worktree
// - 保留原有代码和状态
```

### 参数详解

#### `name` 参数

**格式要求**:
- 只能包含字母、数字、点、下划线、横线
- 每个 `/` 分隔的段最多 64 字符
- 示例: `wp14-skill-hub`, `A0-T1`, `fix/assembly-a1`

**命名约定**（项目实践）:
```
WP 系列:  wp-<number>-<description>
Feature:  <category>-T<number>
Fix:      fix-<description>
Memory:   w<version>-<description>
```

#### `path` 参数

**用途**: 进入已存在的 worktree

**限制**:
- 首次进入：必须在 `git worktree list` 中
- 必须是当前仓库或嵌套子仓库的 worktree
- 必须在 `.claude/worktrees/` 下

**使用时机**:
- 切换到另一个正在进行的工作
- 从主仓库进入 worktree 继续工作
- 在多个 worktrees 之间切换

### 工作流程

```
┌─────────────────────────────────────────┐
│  用户调用 EnterWorktree                  │
└──────────────┬──────────────────────────┘
               │
               ▼
       ┌───────────────┐
       │ 传入 path？    │
       └───┬───────┬───┘
           │ Yes   │ No
           │       │
           │       ▼
           │  ┌─────────────────┐
           │  │ 创建新目录       │
           │  │ .claude/worktrees/│
           │  │ <name>/          │
           │  └────────┬─────────┘
           │           │
           │           ▼
           │  ┌─────────────────┐
           │  │ git worktree add│
           │  │ -b feat/<name>  │
           │  │ <path> origin/main│
           │  └────────┬─────────┘
           │           │
           ▼           ▼
       ┌──────────────────┐
       │ 切换会话工作目录  │
       │ cd <worktree-path>│
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │ 更新会话上下文    │
       │ - CWD            │
       │ - Git branch     │
       │ - Memory files   │
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │ 会话现在在        │
       │ worktree 中工作   │
       └──────────────────┘
```

### 行为特性

#### 1. 分支自动创建

```bash
# 输入
EnterWorktree({ name: 'feature-x' })

# Git 操作
git worktree add \
  -b feat/feature-x-integration \
  .claude/worktrees/feature-x \
  origin/main
```

**分支命名规则**:
- 自动添加前缀: `feat/`, `worktree-`, 等
- 基于 worktree 名称生成
- 从 `origin/main` 分叉

#### 2. Base Ref 配置

可以配置 worktree 从哪个分支分叉：

```json
// settings.json
{
  "worktree": {
    "baseRef": "fresh"  // 默认：从 origin/main
    // 或
    "baseRef": "head"   // 从当前 HEAD
  }
}
```

**选择建议**:
- `fresh`: 独立的新功能开发（推荐）
- `head`: 基于当前工作继续开发

#### 3. 会话隔离

进入 worktree 后，会话被隔离：

```typescript
// 隔离的状态
- 当前工作目录 (CWD)
- Git 分支
- 文件修改不影响主仓库
- 可以独立提交、推送

// 共享的资源
- .git 仓库（对象、配置）
- Git hooks
- 远程仓库引用
```

#### 4. 限制和保护

```typescript
// ❌ 不允许的操作（在 worktree 会话中）
cd /Users/yunpeng/pi-investment  // 被拒绝
git checkout main                 // 会警告

// ✅ 允许的操作
git commit -m "..."
git push origin <branch>
Read/Edit files in worktree
```

---

## 4. ExitWorktree 工具详解

### 工具签名

```typescript
ExitWorktree(params: {
  action: 'keep' | 'remove',
  discard_changes?: boolean  // 仅当 action='remove' 时需要
})
```

### 使用场景

#### 场景 1: 保留 Worktree（工作未完成）

```typescript
ExitWorktree({ action: 'keep' })

// 结果:
// - 退出 worktree 会话
// - 返回主仓库工作目录
// - worktree 目录和分支保留
// - 可以稍后用 EnterWorktree({ path }) 继续
```

**使用时机**:
- 工作进行中，需要切换到主仓库
- 想稍后继续这个工作
- 代码还没有合并到 main

**WP-14 实际执行**:
```bash
# 退出但保留
ExitWorktree({ action: 'keep' })

# 结果
Session returned to: /Users/yunpeng/pi-investment
Worktree preserved at: .claude/worktrees/wp14-skill-hub
Branch preserved: feat/wp14-skill-hub-integration
```

#### 场景 2: 删除 Worktree（工作已完成）

```typescript
ExitWorktree({ action: 'remove' })

// 结果:
// - 退出 worktree 会话
// - 删除 worktree 目录
// - 删除关联的分支
// - 如果有未提交的更改，会被拒绝
```

**前提条件**:
- ✅ 所有更改已提交
- ✅ 分支已合并或推送到远程
- ❌ 有未提交的文件 → 需要 `discard_changes: true`

**示例**:
```typescript
// ❌ 有未提交的更改
ExitWorktree({ action: 'remove' })
// 错误: "Worktree has uncommitted changes"

// ✅ 强制删除
ExitWorktree({ 
  action: 'remove',
  discard_changes: true 
})
```

#### 场景 3: 清理已合并的工作

```bash
# 1. 合并分支到 main
git checkout main
git merge feat/wp14-skill-hub-integration

# 2. 清理 worktree
ExitWorktree({ action: 'remove' })

# 结果: 干净的工作环境
```

### 参数详解

#### `action` 参数（必需）

| 值 | 行为 | 使用场景 |
|---|---|---|
| `keep` | 保留目录和分支 | 工作未完成，稍后继续 |
| `remove` | 删除目录和分支 | 工作已完成，清理环境 |

#### `discard_changes` 参数（可选）

**仅在 `action: 'remove'` 时有效**

```typescript
discard_changes: true
```

**作用**: 强制删除有未提交更改的 worktree

**风险**: ⚠️ 未提交的更改会永久丢失！

**使用场景**:
- 实验性代码，不需要保留
- 错误的开发方向，需要重新开始
- 临时测试，不需要提交

**安全检查**:
```typescript
// Git 会检查
1. 未提交的文件（git status）
2. 未推送的提交（与远程分支对比）

// 如果检测到，会返回错误列表
// 必须明确设置 discard_changes: true 才能删除
```

### 工作流程

```
┌─────────────────────────────────────────┐
│  用户调用 ExitWorktree                   │
└──────────────┬──────────────────────────┘
               │
               ▼
       ┌───────────────┐
       │ action?       │
       └───┬───────┬───┘
           │ keep  │ remove
           │       │
           │       ▼
           │  ┌─────────────────┐
           │  │ 检查未提交更改   │
           │  └────────┬─────────┘
           │           │
           │      ┌────┴────┐
           │      │ 有更改？ │
           │      └─┬─────┬─┘
           │    Yes │     │ No
           │        │     │
           │        ▼     │
           │  ┌──────────┐│
           │  │discard?  ││
           │  └─┬──────┬─┘│
           │ No │      │Yes
           │    ▼      │  │
           │  ❌拒绝   │  │
           │           ▼  ▼
           │      ┌─────────────┐
           │      │ git worktree│
           │      │ remove      │
           │      │ <path>      │
           │      └──────┬──────┘
           │             │
           │             ▼
           │      ┌─────────────┐
           │      │ git branch  │
           │      │ -D <branch> │
           │      └──────┬──────┘
           │             │
           ▼             ▼
       ┌──────────────────┐
       │ 返回主仓库目录    │
       │ cd <main-repo>   │
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │ 清理会话上下文    │
       │ - CWD            │
       │ - Git branch     │
       │ - Memory files   │
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │ 会话现在在        │
       │ 主仓库中工作      │
       └──────────────────┘
```

### 退出时的清理

#### `action: 'keep'`

**保留**:
- ✅ Worktree 目录
- ✅ 分支
- ✅ 所有文件和更改
- ✅ Git 历史

**清理**:
- 🗑️ 会话隔离状态
- 🗑️ CWD 上下文

#### `action: 'remove'`

**删除**:
- 🗑️ Worktree 目录（整个文件夹）
- 🗑️ 关联的分支（本地）
- 🗑️ Git worktree 元数据

**保留**:
- ✅ 已推送到远程的分支
- ✅ 已合并到 main 的更改
- ✅ Git 提交历史（在 reflog 中）

### 注意事项

#### 1. Tmux 会话处理

如果在 worktree 中使用了 tmux：

```bash
# keep 模式
- tmux 会话保持运行
- 可以用 tmux attach 重新连接

# remove 模式
- tmux 会话被终止
- 返回 tmux 会话名称（如果需要清理）
```

#### 2. 只能退出当前会话的 Worktree

```typescript
// ✅ 正确
// 在 worktree 会话中
ExitWorktree({ action: 'keep' })

// ❌ 错误
// 在主仓库中调用
ExitWorktree({ action: 'keep' })
// 返回: "No worktree session active"
```

#### 3. 不影响手动创建的 Worktree

```bash
# 手动创建的 worktree
git worktree add ../my-feature

# ExitWorktree 不会操作它
# 只操作通过 EnterWorktree 创建的 worktree
```

---

## 5. 最佳实践

### 5.1 命名规范

基于项目实际使用：

```bash
# Work Packages (主要开发)
wp-<number>-<description>
例: wp14-skill-hub

# Feature 任务
<category>-T<number>
例: A0-T1, P1-T3

# Bug 修复
fix-<description>
例: fix-assembly-a1

# Memory 系统
w<version>.<sub>-<description>
例: w1.2-memory-api

# 实验性功能
<feature-name>
例: notification-system
```

### 5.2 工作流程

#### 典型的 Worktree 生命周期

```bash
# 1. 创建 worktree（开始新工作）
EnterWorktree({ name: 'wp15-feature' })

# 2. 开发工作
# - 编写代码
# - 提交更改
git add .
git commit -m "feat: implement feature"

# 3. 推送到远程
git push origin feat/wp15-feature-integration

# 4. 完成工作后退出但保留
ExitWorktree({ action: 'keep' })

# 5. 在主仓库中合并
git checkout main
git merge feat/wp15-feature-integration

# 6. 清理 worktree
# 方法 A: 在主仓库手动清理
git worktree remove .claude/worktrees/wp15-feature

# 方法 B: 重新进入再删除
EnterWorktree({ path: '.claude/worktrees/wp15-feature' })
ExitWorktree({ action: 'remove' })
```

### 5.3 何时使用 Worktree

#### ✅ 推荐使用

1. **并行开发多个功能**
   ```bash
   # 同时进行多个 WP
   .claude/worktrees/wp14-skill-hub/    # 正在开发
   .claude/worktrees/wp15-integration/  # 等待测试
   .claude/worktrees/wp16-ui/           # 刚启动
   ```

2. **大型重构或实验**
   ```bash
   # 不影响主分支的安全开发
   EnterWorktree({ name: 'experiment-new-arch' })
   # 失败了可以直接删除
   ExitWorktree({ action: 'remove', discard_changes: true })
   ```

3. **紧急 Bug 修复**
   ```bash
   # 在 wp14 开发中，突然需要修 bug
   ExitWorktree({ action: 'keep' })  # 暂停 wp14
   EnterWorktree({ name: 'hotfix-critical-bug' })
   # 修完后
   ExitWorktree({ action: 'remove' })
   EnterWorktree({ path: '.claude/worktrees/wp14-skill-hub' })  # 继续 wp14
   ```

4. **Code Review**
   ```bash
   # 在不离开当前工作的情况下审查别人的代码
   EnterWorktree({ name: 'review-pr-123' })
   # 审查完
   ExitWorktree({ action: 'remove' })
   ```

#### ❌ 不推荐使用

1. **简单的单文件修改**
   ```bash
   # 不需要 worktree，直接在主分支上改
   git checkout -b fix/typo
   # 修改
   git commit && git push
   ```

2. **线性开发（一次只做一件事）**
   ```bash
   # 如果不需要并行工作，普通分支就够了
   git checkout -b feature-x
   ```

3. **临时查看历史版本**
   ```bash
   # 用 git checkout 就好
   git checkout <commit-hash>
   # 看完后
   git checkout main
   ```

### 5.4 清理策略

#### 定期清理

```bash
# 列出所有 worktrees
git worktree list

# 清理已合并的
for wt in $(git worktree list | grep "feat/" | awk '{print $1}'); do
  branch=$(git -C $wt branch --show-current)
  if git branch --merged main | grep -q $branch; then
    echo "可以清理: $wt"
    # git worktree remove $wt
  fi
done
```

#### 自动清理过期的

```bash
# Git 会自动标记长时间未使用的 worktree 为 prunable
git worktree prune --dry-run  # 预览
git worktree prune            # 执行
```

#### 项目当前状态

```bash
# 统计
总 worktrees: 33
可能需要清理的: ~20 个（已合并或长期未使用）

# 建议
1. 清理所有 A0/A1/A2/A3/P0/P1 系列（功能已完成）
2. 保留 wp14（刚完成，等待验证）
3. 检查其他 wp 系列状态
```

### 5.5 性能优化

#### Worktree 数量建议

```bash
# 推荐
活跃 worktrees: 3-5 个（正在开发的）
保留 worktrees: < 10 个（等待合并/测试的）
总数: < 15 个

# 当前项目
总数: 33 个 ⚠️（超出建议）
建议: 清理已完成的功能分支
```

#### 磁盘空间

```bash
# 每个 worktree 占用空间
du -sh .claude/worktrees/*

# 优化
# - 定期清理已合并的
# - 不要在 worktree 中放大文件
# - node_modules 等可以共享（软链接）
```

---

## 6. 常见问题

### Q1: Worktree 和普通分支有什么区别？

**普通分支**:
```bash
git checkout -b feature-x
# 切换分支，工作目录内容改变
# 同一时间只能在一个分支上工作
```

**Worktree**:
```bash
EnterWorktree({ name: 'feature-x' })
# 创建新目录，可以同时在多个分支上工作
# 不同分支的代码在不同目录
```

### Q2: 为什么不能直接 cd 到主仓库？

Claude Code 的会话隔离机制，防止在 worktree 中误操作主仓库：

```bash
# ❌ 被拒绝
cd /Users/yunpeng/pi-investment

# ✅ 正确做法
ExitWorktree({ action: 'keep' })  # 先退出
# 现在在主仓库中
```

### Q3: 如何在 Worktrees 之间切换？

```bash
# 方法 1: 退出再进入
ExitWorktree({ action: 'keep' })
EnterWorktree({ path: '.claude/worktrees/other-feature' })

# 方法 2: 直接切换（如果支持）
EnterWorktree({ path: '.claude/worktrees/other-feature' })
# 会自动处理之前的 worktree
```

### Q4: Worktree 删除后能恢复吗？

```bash
# 如果已经推送到远程
✅ 可以恢复
git checkout -b feature-x origin/feature-x
git worktree add .claude/worktrees/feature-x feature-x

# 如果只在本地
⚠️ 可能恢复（在 reflog 中）
git reflog  # 查找提交
git checkout -b feature-x <commit-hash>

# 如果用了 discard_changes: true
❌ 无法恢复未提交的更改
```

### Q5: 可以在 Worktree 中创建 Worktree 吗？

```bash
# ❌ 不推荐
# Worktrees 是扁平的，不应该嵌套

# ✅ 正确做法
# 所有 worktrees 都从主仓库创建
ExitWorktree({ action: 'keep' })  # 回到主仓库
EnterWorktree({ name: 'another-feature' })
```

---

## 7. 与 WP-14 实践回顾

### WP-14 中的 Worktree 使用

```bash
# 1. 创建 worktree
EnterWorktree({ name: 'wp14-skill-hub' })

# 创建位置
/Users/yunpeng/pi-investment/.claude/worktrees/wp14-skill-hub/

# 分支
feat/wp14-skill-hub-integration

# 2. 开发过程
# - 3 天开发
# - 4 次 commits
# - 631 行代码

# 3. 完成后退出
ExitWorktree({ action: 'keep' })

# 4. 合并（在主仓库）
git update-ref refs/heads/main refs/heads/feat/wp14-skill-hub-integration
git push origin main

# 5. Worktree 状态
# 目前保留在 .claude/worktrees/wp14-skill-hub/
# 可以随时重新进入或删除
```

### 优势体现

1. **隔离开发**: 不影响主分支和其他功能
2. **并行工作**: 可以同时开发 WP-15（如果需要）
3. **安全实验**: 代码审查和修复在隔离环境中
4. **灵活切换**: 可以暂停去处理紧急任务
5. **清晰组织**: 每个 WP 有独立的目录

---

## 8. 推荐配置

### .gitignore

```bash
# Claude worktrees（通常不需要忽略，因为在 .claude/ 下）
.claude/worktrees/*/node_modules
.claude/worktrees/*/dist
.claude/worktrees/*/.env
```

### Git 配置

```bash
# 自动清理过期的 worktree（默认 3 个月）
git config gc.worktreePruneExpire "90.days.ago"

# 或更激进（30 天）
git config gc.worktreePruneExpire "30.days.ago"
```

### Claude Code 配置

```json
// settings.json (如果存在)
{
  "worktree": {
    "baseRef": "fresh",           // 从 origin/main 分叉
    "autoCleanup": true,           // 退出时提示清理
    "defaultAction": "keep"        // 默认保留 worktree
  }
}
```

---

## 9. 总结

### 核心要点

1. **Worktree 本质**: 同一仓库的多个工作目录
2. **EnterWorktree**: 创建/进入隔离的开发环境
3. **ExitWorktree**: 退出并选择保留或删除
4. **使用场景**: 并行开发、实验、紧急修复、代码审查
5. **最佳实践**: 及时清理、合理命名、定期维护

### 项目建议

针对 pi-investment 项目：

1. **立即行动**:
   - ✅ 清理已合并的 worktrees（A/P 系列）
   - ✅ 减少到 < 15 个活跃 worktrees

2. **工作流程**:
   - ✅ 每个 WP 使用独立 worktree
   - ✅ 完成后及时合并和清理
   - ✅ 保持主仓库干净

3. **命名规范**:
   - ✅ 继续使用 `wp-<number>-<description>` 格式
   - ✅ 保持命名简洁明确

### Worktree vs 普通分支

| 维度 | Worktree | 普通分支 |
|------|----------|----------|
| 并行工作 | ✅ 优秀 | ❌ 不支持 |
| 隔离性 | ✅ 完全隔离 | ⚠️ 需要切换 |
| 磁盘占用 | ⚠️ 多份工作区 | ✅ 单份工作区 |
| 复杂度 | ⚠️ 需要管理 | ✅ 简单 |
| 适用场景 | 大型项目、并行开发 | 简单项目、线性开发 |

### 关键命令速查

```bash
# 创建
EnterWorktree({ name: 'feature-x' })

# 进入已存在的
EnterWorktree({ path: '.claude/worktrees/feature-x' })

# 退出保留
ExitWorktree({ action: 'keep' })

# 退出删除
ExitWorktree({ action: 'remove' })

# 强制删除（有未提交更改）
ExitWorktree({ action: 'remove', discard_changes: true })

# 查看所有 worktrees
git worktree list

# 手动清理
git worktree remove <path>
git worktree prune
```

---

**报告完成日期**: 2026-08-17  
**作者**: Claude (Opus 5)  
**用途**: pi-investment 项目 Worktree 工具使用指南
