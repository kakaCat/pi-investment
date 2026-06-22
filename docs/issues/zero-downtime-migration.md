# 数据库连接池 - 零停机迁移方案

## 🎯 目标

在**不停止服务**的情况下，从旧的连接方式迁移到连接池，彻底解决僵尸连接问题。

## ✅ 已验证的方案

### 核心组件
1. **连接池管理器** - 已实现并通过测试 ✅
2. **BaseRepositoryV2** - 兼容旧代码，向后兼容 ✅
3. **自动迁移工具** - 分析 + 迁移 + 回滚 ✅

### 关键特性
- **零停机**：新旧代码可以并存
- **可回滚**：自动备份，一键恢复
- **渐进式**：可以逐个模块迁移
- **向后兼容**：测试代码无需修改

## 🚀 推荐方案：方案 D - 最小风险迁移

这个方案结合了 A/B/C 的优点，风险最小。

### 步骤 1：配置环境变量

```bash
# 在 .env 中添加连接池配置
cat >> .env << 'EOF'

# 连接池配置
DB_POOL_MIN=5
DB_POOL_MAX=20
EOF
```

### 步骤 2：启用连接池导出

```bash
cd quantsys-v2/infrastructure/database

# 在 __init__.py 中添加
cat >> __init__.py << 'EOF'

# 连接池版本（2026-06-11 启用）
from .base_repository_v2 import BaseRepository as BaseRepositoryV2
from .connection_pool import get_connection_pool, get_cursor, close_pool

__all__ = ['BaseRepository', 'BaseRepositoryV2', 'get_connection_pool', 'get_cursor', 'close_pool']
EOF
```

### 步骤 3：新代码使用连接池（渐进式）

从**现在开始**，所有新写的代码使用 `BaseRepositoryV2`：

```python
# 新代码（推荐）
from infrastructure.database.base_repository_v2 import BaseRepository

class NewRepository(BaseRepository):
    def query_data(self):
        with self._get_cursor() as cursor:
            cursor.execute("SELECT ...")
            return cursor.fetchall()
```

旧代码保持不变，继续使用 `base_repository.py`，但会逐渐减少。

### 步骤 4：监控验证

```bash
# 每小时自动监控
crontab -e
# 添加：
0 * * * * /path/to/scripts/monitor-db-connections.sh >> /tmp/connection-monitor.log 2>&1
```

---

## 📊 方案对比

| 方案 | 风险 | 时间 | 可回滚 | 推荐度 |
|------|------|------|--------|--------|
| A. 全量替换 | 🔴 高 | 1天 | ⚠️ 困难 | ⭐ |
| B. 渐进迁移 | 🟡 中 | 1周 | ✅ 容易 | ⭐⭐⭐ |
| C. 观望测试 | 🟢 低 | 2周 | ✅ 容易 | ⭐⭐ |
| **D. 最小风险** | 🟢 **极低** | **2天** | ✅ **即时** | ⭐⭐⭐⭐⭐ |

---

## 🎬 快速启动脚本

```bash
#!/bin/bash
# quick_start_pool.sh - 快速启用连接池

set -e

echo "🚀 开始启用连接池..."

# 1. 配置环境变量
if ! grep -q "DB_POOL_MIN" .env 2>/dev/null; then
    echo "" >> .env
    echo "# 连接池配置（2026-06-11 添加）" >> .env
    echo "DB_POOL_MIN=5" >> .env
    echo "DB_POOL_MAX=20" >> .env
    echo "✓ 已添加连接池配置"
fi

# 2. 创建 __init__.py 导出
cd quantsys-v2/infrastructure/database
if ! grep -q "BaseRepositoryV2" __init__.py 2>/dev/null; then
    cat >> __init__.py << 'EOF'

# 连接池版本（2026-06-11 启用）
from .base_repository_v2 import BaseRepository as BaseRepositoryV2
from .connection_pool import get_connection_pool, get_cursor, close_pool

__all__ = ['BaseRepository', 'BaseRepositoryV2', 'get_connection_pool', 'get_cursor', 'close_pool']
EOF
    echo "✓ 已启用连接池导出"
else
    echo "✓ 连接池已存在，跳过"
fi

cd ../../..

echo ""
echo "✅ 连接池已启用！"
echo ""
echo "下一步："
echo "  1. 重启 quantsys-v2: cd quantsys-v2 && python start_all.py"
echo "  2. 监控连接数: ./scripts/monitor-db-connections.sh"
echo "  3. 新代码使用: from infrastructure.database.base_repository_v2 import BaseRepository"
```

---

## 🔍 验证清单

### 启用后 1 小时
- [ ] 服务正常运行（无错误日志）
- [ ] 连接数 < 30
- [ ] API 响应正常

### 启用后 24 小时
- [ ] 连接数稳定（无持续增长）
- [ ] 无僵尸连接累积
- [ ] 性能无明显下降

---

## 💡 执行建议

1. **现在（5分钟）**：创建并执行 `quick_start_pool.sh`
2. **今天（1小时）**：重启服务 + 监控验证
3. **本周（渐进）**：新功能使用 BaseRepositoryV2
4. **下周（优化）**：迁移高频 Repository
