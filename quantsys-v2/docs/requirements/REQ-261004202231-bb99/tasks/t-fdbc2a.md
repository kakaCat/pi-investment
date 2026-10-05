# t-fdbc2a [重做] 删除 domain/memory 领域实现

> 需求：REQ-261004202231-bb99 quantsys-v2 记忆子系统下线：清引用后删除端点/领域/仓储/测试

## 在做什么
[重做] 删除 domain/memory 领域实现

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
① grep -rn 'MemoryService|MemoryRepository|domain.memory' domain/ application/ adapters/ infrastructure/ → 返回 0 命中；② 重启 v2 后启动日志不含 ImportError。

---
## 汇报 1（2026-10-05T02:01:45.492Z，窗口 session-ebe42d9f-2797-48c7-b069-3d24d1da6184）

v2 的记忆领域层彻底移除：domain/memory 六个文件删除，连实现被删后成空壳的 IMemoryRepository 端口也一并清掉。

### 完成项

- 删 domain/memory（service/hybrid_search/embedding/distiller/models/__init__）
- 删 domain/ports 里已成空壳的 IMemoryRepository 及其导入与 __all__ 条目
- 自测：全仓记忆符号 grep 0 命中；v2 重启后 /api/health 200

### 改动文件

- `quantsys-v2/domain/ports/repository_ports_extended.py`
- `quantsys-v2/domain/ports/__init__.py`

### 下一步

测试删除由 t-611597 承接。

---
