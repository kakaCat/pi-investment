#!/bin/bash
# 对比 Flask 和 FastAPI 的 API 实现

echo "=========================================="
echo "Flask vs FastAPI API 对比"
echo "=========================================="
echo ""

# 1. 检查 Flask 备份中的路由文件
echo "1. Flask 路由文件（备份）:"
echo "------------------------------------------"
if [ -d "archived/flask_backup_20260629_152409/api/routes" ]; then
    flask_routes=$(find archived/flask_backup_20260629_152409/api/routes -name "*.py" ! -name "__init__.py" | wc -l)
    echo "Flask 路由文件数: $flask_routes"
    echo ""
    echo "Flask 路由列表:"
    find archived/flask_backup_20260629_152409/api/routes -name "*.py" ! -name "__init__.py" -exec basename {} .py \; | sort
else
    echo "❌ Flask 备份目录不存在"
fi

echo ""
echo "2. FastAPI 路由文件:"
echo "------------------------------------------"
if [ -d "adapters/inbound/fastapi_app/routes" ]; then
    fastapi_routes=$(find adapters/inbound/fastapi_app/routes -name "*_async.py" | wc -l)
    echo "FastAPI 路由文件数: $fastapi_routes"
    echo ""
    echo "FastAPI 路由列表:"
    find adapters/inbound/fastapi_app/routes -name "*_async.py" -exec basename {} _async.py \; | sort
else
    echo "❌ FastAPI 路由目录不存在"
fi

echo ""
echo "3. 对比分析:"
echo "------------------------------------------"

# 创建临时文件
flask_list=$(mktemp)
fastapi_list=$(mktemp)

if [ -d "archived/flask_backup_20260629_152409/api/routes" ]; then
    find archived/flask_backup_20260629_152409/api/routes -name "*.py" ! -name "__init__.py" -exec basename {} .py \; | sort > $flask_list
fi

if [ -d "adapters/inbound/fastapi_app/routes" ]; then
    find adapters/inbound/fastapi_app/routes -name "*_async.py" -exec basename {} _async.py \; | sort > $fastapi_list
fi

# 找出 Flask 有但 FastAPI 没有的
echo "Flask 有但 FastAPI 缺失的路由:"
while read route; do
    if ! grep -q "^${route}$" $fastapi_list; then
        echo "  ❌ $route"
    fi
done < $flask_list

echo ""
echo "FastAPI 有但 Flask 没有的路由:"
while read route; do
    if ! grep -q "^${route}$" $flask_list; then
        echo "  ➕ $route"
    fi
done < $fastapi_list

echo ""
echo "两者都有的路由:"
while read route; do
    if grep -q "^${route}$" $fastapi_list; then
        echo "  ✅ $route"
    fi
done < $flask_list

# 清理
rm -f $flask_list $fastapi_list

echo ""
echo "=========================================="
echo "对比完成"
echo "=========================================="
