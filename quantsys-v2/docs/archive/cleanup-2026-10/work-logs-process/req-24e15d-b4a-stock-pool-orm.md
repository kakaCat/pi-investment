# REQ-24e15d 批次 B4-a —— stock_pool_repository 真落 ORM（10 处）

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-14
- **范围**：`adapters/outbound/repositories/stock_pool_repository.py`（10 处）

---

## 1. 这个文件的注释本身就在打脸

文件头写着（2026-08-04）：

> ORM 重构把本仓储换成缺 dict 契约的残版…**按归档 8f06ae1^ 版本恢复旧实现**

而那个"旧实现"**本身就是 db_cursor + 10 处裸 SQL** —— 也就是说：
当年为了"恢复功能"把 ORM 回退成了裸 SQL，然后就这么留了一个多月。

本批把它真正落到 ORM：类改为继承 `BaseORMRepository[StockPool]`（拿到 scoped_session、
commit/rollback、`_safe_rollback` 的线程防毒化），SQL 全部消失，
JSONB 直接传 Python 对象（不再手工 `json.dumps`）。

## 2. 对外契约逐条保持（这是本批最花心思的地方）

| 语义 | 是否保持 | 说明 |
|---|---|---|
| `create(data) → dict` | ✅ | 提交后再读回（原注释解释了为什么必须"提交后再读"） |
| `update` 只改**白名单**字段 | ✅ | `_UPDATABLE_FIELDS` 常量，与旧 `allowed` 集合一致 |
| `update` **跳过 None** | ✅ | 实测传入 `description=None` 后原值不变 |
| `update` **静默忽略未知字段** | ✅ | 实测传 `pool_type='dynamic'` 后仍是 `static` |
| `update_symbols` 同时刷 last_refreshed_at | ✅ | |
| 找不到池 → 返回 None / False | ✅ | 五个写方法逐一实测 |
| `_parse_row` 的 JSONB 兼容分支 | ✅ | ORM 读出来已是对象，该分支正常不触发（保留以免形状变化） |

## 3. 验证证据（真库 · 10 个方法全覆盖）

对合成池做完整 round-trip（用完即删）：

```
create: 62 ['600519','000001'] {'pe': [0,20]} static      # filter_template 直接是 dict，不是字符串
update: zz-b4-test2
update skip None: d                                        # None 被跳过 ✓
update unknown field ignored: static                       # 未知字段被忽略 ✓
update_symbols: ['600000'] True                            # last_refreshed_at 已刷 ✓
update_validation: {'ok': True}
scan_enabled before: True → update_scan_enabled: True False
update_signal_scan: {'buy': 3}
delete: True then get: None
delete missing: False / update missing: None / update_symbols missing: None / scan_enabled missing: False
```

读路径：`get_all()` 28 个池、`get_dynamic_pools()` 3 个、`get_pool()` 与 `get_by_id()` 等价。

## 4. 本批发现的两个值得记的事

### 4.1 一个既有缺陷：`signals.action_type` 模型/库结构漂移

`models/signal.py` 声明 `action_type = Column(Integer, nullable=False)` **无默认值**，
而库里该列也是 NOT NULL 且无默认 → 任何不带 `action_type` 的 ORM 插入必然
`NotNullViolation`。

后果：`tests/services/test_heatmap_service.py` **10 errors**、
`tests/repositories/test_heatmap_repository_events.py` **7 errors**
—— 两者已用 HEAD worktree 复现确认**在 HEAD 上同样失败**，与本批无关。
留给后续（要么给模型加默认值，要么让建表脚本给列默认值）。

### 4.2 一个执行教训：一次 aborted 事务会污染整条测试链

上面那个 NotNullViolation 让 **scoped_session 进入 aborted 状态**，
后续用例连续报 **26 个 `PendingRollbackError`**（表现为"完全不相关的测试也全红了"）。
逐个文件单独跑时：`test_experience_accumulator` **6 passed**、`test_chan_jobs` **5 passed**。

> 判读纪律：**批量回归出大面积红时，先看第一条错**（这里是 NotNullViolation），
> 后面几十条往往是它的级联回声。也正因如此，本仓的仓储方法普遍带 `_safe_rollback`。

## 5. 指标变化

| 指标 | B3-b 后 | B4-a 后 | 变化 |
|---|---|---|---|
| cursor_execute | 72 | **62** | −10 |

`stock_pool_repository.py` CLEAN；`--gate` 退出码 0。
