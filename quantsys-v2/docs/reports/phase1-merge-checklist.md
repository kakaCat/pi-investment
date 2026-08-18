# Phase 1 合并前检查清单

**分支**: `feat/phase1-exception-logging`  
**目标**: 合并到 `main`  
**日期**: 2026-08-18

## ✅ 完成的工作

### 1. 异常体系建立
- [x] 创建 `domain/exceptions.py` (8个异常类)
- [x] 修改 `main.py` 添加分层异常处理器
- [x] 示范修改 `data_service.py`

### 2. Lint 规则配置
- [x] 创建 `.ruff.toml` 配置文件
- [x] 禁止新增 `print()` 和裸 `except`
- [x] 豁免 scripts/tools/tests/debug 文件
- [x] 豁免低优先级代码（quantlib/Flask旧代码）

### 3. 迁移工具
- [x] `scripts/migrate_exceptions.py` - 异常迁移分析工具
- [x] `scripts/migrate_print_to_logger.py` - print 迁移工具

### 4. 文档
- [x] `docs/reports/phase1-completion-report.md` - 完成报告

## ✅ 提交记录

```
676fe01 feat(phase1): 添加迁移工具和完成报告
2146704 feat(phase1): 建立业务异常层次结构和 lint 规则
```

## 验证检查项

### 代码质量
- [x] `domain/exceptions.py` 语法正确
- [x] `data_service.py` 语法正确  
- [x] 异常类可正常导入
- [ ] 运行单元测试（需要在合并前执行）
- [ ] 启动 FastAPI 服务验证

### 代码审查
- [x] 新增文件有明确用途
- [x] 修改文件有清晰的变更说明
- [x] 提交信息清晰规范
- [x] 无敏感信息泄露

### 文档完整性
- [x] 有实施计划（原计划）
- [x] 有完成报告
- [x] 代码有注释说明
- [x] 异常类有使用示例

## 合并前必做

### 1. 运行测试（在 worktree 中）
```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/phase1-exception-logging/quantsys-v2
source activate-py313.sh
pytest tests/ -v --tb=short -x
```

### 2. 验证服务启动（在 worktree 中）
```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/phase1-exception-logging/quantsys-v2
python -c "from adapters.inbound.fastapi_app.main import app; print('✅ FastAPI app can import')"
```

### 3. 合并步骤
```bash
# 1. 切换到主工作区
cd /Users/yunpeng/pi-investment

# 2. 确保 main 最新
git checkout main
git pull origin main

# 3. 合并 feature 分支
git merge feat/phase1-exception-logging --no-ff -m "Merge Phase 1: 异常体系与日志统一基础设施

- 建立8个业务异常类层次结构
- 添加分层异常处理器（8种HTTP状态码）
- 配置lint规则防止新增问题
- 提供迁移工具辅助后续工作
- 示范修改核心文件

详见: quantsys-v2/docs/reports/phase1-completion-report.md"

# 4. 推送到远程
git push origin main

# 5. 删除 feature 分支（可选）
git branch -d feat/phase1-exception-logging
git worktree remove .claude/worktrees/phase1-exception-logging
```

## 合并后工作

### 1. 通知团队
- [ ] 更新 CLAUDE.md 说明新的异常体系
- [ ] 通知其他开发者使用新异常类型
- [ ] 分享迁移工具使用方法

### 2. 开始 Phase 2
- [ ] 创建新的 worktree: `feat/phase2-architecture-cleanup`
- [ ] 删除 Flask 路由
- [ ] 路由注册失败中断启动

## 风险评估

| 风险 | 等级 | 缓解措施 | 状态 |
|------|------|---------|------|
| 新异常类型影响现有代码 | 低 | 只新增，不破坏现有代码 | ✅ 已控制 |
| lint 规则过严导致无法提交 | 中 | 豁免了大部分旧代码 | ✅ 已缓解 |
| 测试失败 | 中 | 合并前必须运行测试 | ⏳ 待执行 |
| 服务启动失败 | 低 | 只修改了异常处理，不改业务逻辑 | ⏳ 待验证 |

## 回滚计划

如果合并后发现问题：

```bash
# 1. 快速回滚
git revert HEAD -m 1

# 2. 或者硬重置（如果未推送远程）
git reset --hard HEAD~1

# 3. 保留修改但撤销合并
git reset --soft HEAD~1
```

## 后续任务追踪

**P0 - 高优先级**（Phase 2-3）:
- [ ] 删除 Flask 路由（62个文件）
- [ ] 路由注册失败中断启动
- [ ] 迁移 application/services 异常（543个）
- [ ] 迁移 adapters/routes 异常（259个）

**P1 - 中优先级**（Phase 3-4）:
- [ ] 迁移直接 akshare 导入（67个文件）
- [ ] 清理 sys.path.insert（236处）
- [ ] TODO/FIXME 清理（113处）
- [ ] 线程统一管理（34处）

**P2 - 低优先级**（Phase 4+）:
- [ ] domain/quantlib 异常迁移（277个）
- [ ] domain/quantlib print 迁移（1,277个）

---

**检查人**: Claude (AI Agent)  
**检查日期**: 2026-08-18  
**状态**: ⏳ 等待测试验证后合并
