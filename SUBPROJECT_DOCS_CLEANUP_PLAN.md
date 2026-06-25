# 子项目文档清理方案

## 概述

三个子项目（agent-ts、quantsys-v2、web-frontend）都存在大量临时报告文档需要整理。

## agent-ts/ 清理方案

### 保留（2个文件）
- ✅ `CLAUDE.md` - 子项目指引
- ✅ `README.md` - 子项目说明

### 建议归档到 agent-ts/.archive/2026-06-reports/（8个文件）
- `QUANT_CLI_REFACTOR_COMPLETE.md`
- `QUANT_CLI_REFACTOR_PLAN.md`
- `QUANT_CLI_REVIEW_TEST_REPORT.md`
- `REVIEW_SUGGESTIONS.md`
- `TASK_COMPLETION_REPORT.md`
- `TEST_FIX_PLAN.md`
- `TEST_ISSUES_REPORT.md`
- `TOOL_AUDIT_REPORT.md`

## quantsys-v2/ 清理方案

### 保留（4个文件）
- ✅ `CLAUDE.md` - 子项目指引
- ✅ `README.md` - 子项目说明（如果存在）
- ✅ `AGENTS.md` - Agent 对接说明
- ✅ `DATA_PIPELINE_GUIDE.md` - 数据管道指南

### 建议归档到 quantsys-v2/.archive/2026-06-reports/（至少6个文件）
- `BUGFIX_analysis_buy_range.md`
- `CHECKLIST.md`
- `COMPLETE_PROJECT_REPORT.md`
- `CURSOR_FIX_FINAL_SUMMARY.md`
- `CURSOR_FIX_REPORT.md`
- `CURSOR_FIX_SUMMARY.md`
- `CURSOR_FIX_TEST_REPORT.md`
- 其他 `*_REPORT.md`、`*_SUMMARY.md` 等临时文档

### 需要单独检查
quantsys-v2 有更多文档，需要完整列表后分类：
```bash
cd quantsys-v2 && ls -1 *.md
```

## web-frontend/ 清理方案

### 保留（4个文件）
- ✅ `CLAUDE.md` - 子项目指引
- ✅ `README.md` - 子项目说明
- ✅ `README-CICD.md` - CI/CD 说明
- ✅ `README-INFRASTRUCTURE.md` - 基础设施说明

### 建议归档到 web-frontend/.archive/2026-06-reports/（7个文件）
- `BACKEND_FIX_TEST_REPORT.md`
- `BACKEND_INTEGRATION_REPORT.md`
- `COMPLETE-REPORT.md`
- `COMPLETION-REPORT.md`
- `FINAL-REPORT.md`
- `PROGRESS-REPORT.md`
- `PROTOTYPE-COMPARISON.md`

### 可能保留（需要检查内容）
- `style-alignment-status.md` - 如果是持续维护的规范文档则保留，否则归档

## 实施步骤

### 1. agent-ts 清理
```bash
cd agent-ts
mkdir -p .archive/2026-06-reports
mv QUANT_CLI_*.md .archive/2026-06-reports/
mv REVIEW_SUGGESTIONS.md .archive/2026-06-reports/
mv TASK_COMPLETION_REPORT.md .archive/2026-06-reports/
mv TEST_*.md .archive/2026-06-reports/
mv TOOL_AUDIT_REPORT.md .archive/2026-06-reports/
```

### 2. quantsys-v2 清理
```bash
cd quantsys-v2
mkdir -p .archive/2026-06-reports
# 先列出所有 .md 文件，人工确认后执行
ls -1 *.md > /tmp/quantsys_docs.txt
# 然后根据确认结果移动文件
```

### 3. web-frontend 清理
```bash
cd web-frontend
mkdir -p .archive/2026-06-reports
mv BACKEND_*.md .archive/2026-06-reports/
mv *-REPORT.md .archive/2026-06-reports/
mv PROTOTYPE-COMPARISON.md .archive/2026-06-reports/
```

### 4. 更新子项目 .gitignore
在每个子项目的 .gitignore 中添加：
```gitignore
# Temporary reports and work documents
*_REPORT.md
*_SUMMARY.md
*_COMPLETE.md
*_STATUS.md
*-REPORT.md
*-SUMMARY.md

# Keep subproject core docs
!CLAUDE.md
!README*.md
```

## 自动化脚本

可以创建 `cleanup-subproject-docs.sh` 脚本来自动执行：
```bash
#!/bin/bash
# 清理所有子项目的临时文档

# agent-ts
cd agent-ts
mkdir -p .archive/2026-06-reports
mv QUANT_CLI_*.md REVIEW_*.md TASK_*.md TEST_*.md TOOL_*.md .archive/2026-06-reports/ 2>/dev/null
cd ..

# web-frontend
cd web-frontend
mkdir -p .archive/2026-06-reports
mv BACKEND_*.md *-REPORT.md PROTOTYPE-*.md .archive/2026-06-reports/ 2>/dev/null
cd ..

# quantsys-v2 需要手动处理（子模块）
echo "quantsys-v2 is a submodule, please clean it separately"
```

## 注意事项

1. **quantsys-v2 是子模块**：需要在其目录内单独执行 git 操作
2. **检查内容后再移动**：某些 `*_GUIDE.md` 可能是长期文档，不应归档
3. **保持一致性**：所有子项目使用相同的归档策略
4. **更新 .gitignore**：防止未来再次提交临时文档

## 统计

- **agent-ts**: 10个文档 → 保留2个，归档8个
- **web-frontend**: 12个文档 → 保留4个，归档7-8个
- **quantsys-v2**: 需要完整统计（子模块，大量文档）

---

**创建时间**: 2026-06-26
**状态**: 待执行
