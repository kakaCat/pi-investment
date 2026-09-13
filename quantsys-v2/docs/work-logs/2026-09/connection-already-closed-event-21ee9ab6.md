# 错误事件处置：API 错误 connection already closed（21ee9ab6，裸连接空闲事务）

- **事件 ID**：`21ee9ab6-8a92-406f-b71a-3ccb3fb06253`（source=v2，error，频次 1，09-12 19:12）
- **处置窗口**：w-32314d00（原派单窗口 w-c8cae280）

## 1. 原始 traceback 给出的完整链条（看板卡片里才有）

```
signal_tracking_repository.py:106  update_signal_performance → cursor.execute(sql, values)
    psycopg2.OperationalError: terminating connection due to idle-in-transaction timeout
      server closed the connection unexpectedly
signal_tracking_repository.py:110  → self.db.rollback()
    psycopg2.InterfaceError: connection already closed
```

→ 对外的错误文本是 **"connection already closed"（次生异常）**，真因 **idle-in-transaction 超时**被完全掩盖。

## 2. 根因（两个缺陷叠加）

1. **读方法不结束事务**：`SignalTrackingRepository` 自建并长期持有 psycopg2 裸连接（`__init__` 里 `psycopg2.connect(...)`），
   而 `get_signals_by_date` / `get_signals_after_date` / `get_signals` 只 `cursor.close()`、**从不 commit/rollback**；
   psycopg2 在第一条语句处隐式开启事务 → 两次调用之间连接**空闲在事务中** → 超过 PostgreSQL 的
   `idle_in_transaction_session_timeout` 被服务端杀连接 → 下一次写操作必然 bomb。
2. **错误处理掩盖真因且不自愈**：`except` 对**已死连接**调 `rollback()` → `InterfaceError` 顶替原始 `OperationalError`；
   且 `self.db` 永不重建 → 之后每次调用继续失败。

> 与本日已处置的 `session_leak_detected`（a6780ec3）**同族**：都是"事务没结束 → 连接空闲占用"，
> 区别只是 ORM scoped_session vs 裸连接。ORM 侧已修，本次补齐裸连接侧。

## 3. 落地动作（`adapters/outbound/repositories/signal_tracking_repository.py`）

1. `_end_read()`：**所有方法**（读写共 6 处）退出前统一结束事务（`finally` 里调用）；
2. `_safe_rollback(context)`：回滚失败（连接已死）时**先记原始错误**、不让次生异常顶替真因，并丢弃死连接（`self.db = None`）；
3. `_ensure_connection()`：连接为 `None` 或 `closed` 时**自愈重建**，避免一次断连后永久失效；
4. 所有 `except` 改为「先 logger.error(原始异常) → `_safe_rollback` → `raise`（原始异常）」。

## 4. 验证

```console
$ pytest tests/test_signal_tracking_connection.py -q            → 5 passed
     · 读后必须结束事务（rollback 调用 ≥1）
     · 死连接回滚失败时仍抛原始 OperationalError（含 idle-in-transaction 字样），且丢弃连接
     · closed 连接自愈重建；健康连接不重建

$ # 重启后实测「原失败端点」
PUT /api/signals/track/update  → HTTP 200 / 0.82s  {"success": true, "data": {"updated": 0, ...}}
日志：signal_performance_updated（info）· PUT ... - 200 - 0.823s，无异常

$ grep -c "connection already closed" logs/launchd-stdout.log → 1（仅 09-12 那次历史记录；重启后 0 次）
```

**卡片结论已更正**：本卡此前由本窗口在"僵尸卡清理"批中代写闭环（归因偏浅），收到完整 traceback 后
以真因重开并重新闭环（note 1123 字，含证据链）。

## 5. 通用纪律

- **裸连接同样要"用完即结束事务"**：psycopg2 的隐式事务不会自己消失，长寿命连接空闲在事务中等同占坑；
- **except 里先记原始异常**：任何清理动作（rollback/close）都必须包 try，否则次生异常会顶替真因、把排障带偏；
- **连接自愈**：连接对象要能检测 `closed` 并重建，不能一次断连就永久变砖。