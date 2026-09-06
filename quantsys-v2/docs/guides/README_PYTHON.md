# Python 版本说明

## 当前配置

本项目已配置为统一使用 **Python 3.13.12** (Homebrew版本)。

## 为什么需要 Python 3.13?

原代码中使用了 `Dict | List` 类型联合语法，这是 Python 3.10+ 的特性。虽然已将代码修改为使用 `Optional[Any]` 以兼容旧版本，但为了更好的类型支持和未来的维护，建议使用 Python 3.13。

## 启动服务

### 推荐方式（使用 Python 3.13）

```bash
cd quantsys-v2
./start.sh
```

`start.sh` 脚本会明确使用 `/opt/homebrew/bin/python3.13` 启动服务。

### 备用方式

```bash
cd quantsys-v2
./start_with_py313.sh
```

### 手动启动

```bash
cd quantsys-v2
/opt/homebrew/bin/python3.13 start_all.py
```

## 系统中的 Python 版本

- `/usr/local/bin/python3` → Python 3.8.10 (系统默认)
- `/opt/miniconda3/bin/python` → Python 3.12.8 (Conda)
- `/opt/homebrew/bin/python3.13` → Python 3.13.12 (推荐使用)

## 符号链接

已在 `/opt/homebrew/bin/` 创建以下链接：

```
python3 -> python3.13
python -> python3.13
pip3 -> pip3.13
pip -> pip3.13
```

## 代码兼容性

所有路由文件中的类型注解已修改为兼容 Python 3.8+：
- `Optional[Dict | List]` → `Optional[Any]`
- 所有文件已添加 `from typing import Any`

## 验证

启动服务后，可以通过以下方式验证：

```bash
# 检查API是否正常
curl http://127.0.0.1:5001/api/sentiment/market
curl -X POST http://127.0.0.1:5001/api/signals/scan -H "Content-Type: application/json" -d '{}'

# 查看已注册的端点数量
curl -s http://127.0.0.1:5001/openapi.json | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('paths', {})))"
```

应该看到：
- ✅ sentiment/market 正常响应
- ✅ signals/scan 正常响应  
- ✅ 90个API端点已注册

## 故障排查

### 404 错误

如果遇到 API 404 错误：

1. 检查服务是否启动：`ps aux | grep start_all`
2. 检查端口占用：`lsof -iTCP:5001 -sTCP:LISTEN`
3. 查看启动日志：`tail -100 /tmp/quantsys_fastapi.log`
4. 重启服务：
   ```bash
   pkill -9 -f "start_all.py"
   cd quantsys-v2
   ./start.sh > /tmp/quantsys_fastapi.log 2>&1 &
   ```

### Python 版本问题

如果服务使用了错误的 Python 版本：

1. 使用 `start.sh` 脚本启动（明确指定 Python 3.13）
2. 检查 Python 链接：`ls -la /opt/homebrew/bin/python*`
3. 验证版本：`/opt/homebrew/bin/python3.13 --version`
