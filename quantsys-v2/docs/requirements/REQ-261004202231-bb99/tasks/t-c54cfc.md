# t-c54cfc [重做] 摘除 v2 记忆路由注册点

> 需求：REQ-261004202231-bb99 quantsys-v2 记忆子系统下线：清引用后删除端点/领域/仓储/测试

## 在做什么
[重做] 摘除 v2 记忆路由注册点

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
① 对 v2 启动日志 logs/launchd-api.log 执行 grep -c 'Registered: memory' → 返回 0；② 同一日志 grep 'optional_failed' 的条目与删除前一致（不变）；③ 复核 adapters/inbound/fastapi_app/main.py 不含 memory 字面量。

---
## 汇报 1（2026-10-05T02:01:44.452Z，窗口 session-ebe42d9f-2797-48c7-b069-3d24d1da6184）

v2 侧的记忆路由不再注册：启动日志里没有 memory 的注册行、也没有导入失败告警，其余模块照常注册。

### 完成项

- 删掉 route_registrar 的两条记忆路由表项（方法名随之从 register_memory_routes 改为 register_knowledge_routes，定义与唯一调用点同步）
- 删掉 main.py 的两段 include_router，并不留宽容导入分支
- 自测：最近一次重启的日志里 Registered: memory 0 次、Failed to import memory 0 次

### 改动文件

- `quantsys-v2/adapters/inbound/fastapi_app/route_registrar.py`
- `quantsys-v2/adapters/inbound/fastapi_app/main.py`

### 下一步

端点与仓储删除已由 t-3a0393 承接。

---
