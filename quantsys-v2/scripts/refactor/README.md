# QuantSys V2 中等问题重构 - README

快速命令参考 (使用 Makefile)

## 🚀 快速开始

```bash
# 1. 查看所有命令
make help

# 2. 安装项目
make install

# 3. 查看当前状态
make verify

# 4. 运行演示
make demo
```

## 📊 常用命令

### 验证状态
```bash
make verify              # 验证修复状态
make scan-imports        # 扫描违规导入
make scan-todos          # 扫描 TODO
make scan-syspath        # 扫描 sys.path.insert
```

### 自动修复
```bash
make auto-fix-dry        # 预览修复（不修改）
make auto-fix            # 实际修复（需确认）
make fix-syspath         # 只修复 sys.path.insert
make format              # 代码格式化
```

### 进度跟踪
```bash
make progress            # 保存进度快照
make history             # 查看历史
make report              # 生成报告
```

### 测试
```bash
make test                # 运行所有测试
make test-quick          # 快速测试
make lint                # 代码检查
```

## 📚 完整文档

详见:
- `docs/refactor/README.md` - 项目总览
- `docs/refactor/QUICKSTART.md` - 快速指南
- `docs/refactor/EXECUTIVE-SUMMARY.md` - 执行摘要
- `docs/refactor/medium-issues-solution.md` - 技术方案

## 🛠️ 工具清单

| 工具 | 用途 |
|------|------|
| `verify_fixes.py` | 验证修复状态 |
| `find_direct_imports.py` | 查找违规数据源导入 |
| `classify_todos.py` | TODO 分类统计 |
| `remove_sys_path_hacks.py` | 移除 sys.path.insert |
| `track_progress.py` | 进度追踪 |
| `demo.sh` | 一键演示 |
| `auto-fix.sh` | 自动修复 |
| `generate_report.sh` | 生成报告 |

## ⚙️ 配置文件

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python 包配置 |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `Makefile` | 快捷命令 |

## 🎯 验收标准

运行 `make verify`，所有检查通过：

```
✅ sys.path.insert 清理             0 处
✅ 数据源直接导入清理               核心模块 0 处
✅ 日志系统统一                     100% structlog
✅ 线程统一管理                     100% ThreadManager
✅ 配置统一管理                     单一入口
✅ Webhook 非阻塞                   使用任务队列
✅ TODO/FIXME                       P0/P1 全部修复

🎉 所有中等问题已修复！
```

## 📞 需要帮助？

- 运行 `make help` 查看所有命令
- 阅读 `docs/refactor/QUICKSTART.md` 获取详细指导
- 查看 `docs/refactor/medium-issues-solution.md` 了解技术细节
