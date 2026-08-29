#!/bin/bash
# 生成重构报告 - 生成完整的状态报告用于周报/月报

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_FILE="${1:-docs/refactor/status-report-$(date +%Y%m%d).md}"

cd "$PROJECT_ROOT"

echo "生成重构状态报告..."

cat > "$REPORT_FILE" << 'EOF'
# QuantSys V2 中等问题重构状态报告

**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')

## 📊 问题修复状态

EOF

# 运行验证脚本
python scripts/refactor/verify_fixes.py >> "$REPORT_FILE" 2>&1

cat >> "$REPORT_FILE" << 'EOF'

## 📈 详细统计

### 1. sys.path.insert 使用情况

EOF

echo '```' >> "$REPORT_FILE"
python scripts/refactor/remove_sys_path_hacks.py 2>&1 | head -30 >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"

cat >> "$REPORT_FILE" << 'EOF'

### 2. 数据源直接导入统计

EOF

echo '```' >> "$REPORT_FILE"
python scripts/refactor/find_direct_imports.py 2>&1 | head -50 >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"

cat >> "$REPORT_FILE" << 'EOF'

### 3. TODO/FIXME 统计

EOF

echo '```' >> "$REPORT_FILE"
python scripts/refactor/classify_todos.py 2>&1 | head -50 >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"

cat >> "$REPORT_FILE" << 'EOF'

## 📝 本周完成

- [ ] 待填写

## 🎯 下周计划

- [ ] 待填写

## 🚨 风险和阻塞

- 无

## 💡 建议

- 继续按计划执行

---

**报告人**: [姓名]  
**下次更新**: [日期]
EOF

echo "✅ 报告已生成: $REPORT_FILE"
echo ""
echo "📝 下一步:"
echo "  1. 编辑报告填写 '本周完成' 和 '下周计划'"
echo "  2. 发送给团队或添加到文档"
