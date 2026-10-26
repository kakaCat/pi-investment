# t-c1ce88 待办证据列与部分索引·复核

> 需求：REQ-261021194640-69b8 盯盘执行闭环三接缝：成交回写·消息投递·待办闭环

## 在做什么
待办证据列与部分索引·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/REQ-261021194640-69b8/design/` 逐条核对；`npx vitest run tests/` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-21T12:20:34.705Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：表结构与迁移语义无偏离；唯一口径差异是缺列库读路径改为响亮报错（fail-loud），理由与依据已登记，两库迁移已先行完成。

### 完成项

- 表结构核对：evidence jsonb 可空、部分索引谓词 terminal IS NULL，与 data-model 一致
- 迁移口径核对：默认 dry-run、--apply、--dsn、IF NOT EXISTS 幂等、无回填
- 命名核对：迁移文件名与索引名与设计逐字一致
- 口径修正：缺列库读路径选择响亮报错而非返回 None，已在注释登记（避免把有证据伪装成无证据）
- 余下均无偏离

### 改动文件

- `../../infrastructure/persistence/migrations/20261021_watch_todos_evidence.py`
- `../../infrastructure/persistence/orm/models/watch_todo.py`
- `../../adapters/outbound/repositories/watch_todo_repository.py`

### 下一步

测试段：复跑仓储验收与相邻回归

---
