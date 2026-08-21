# 框架约束快速参考

> **TL;DR**: Session 必须用 with；写后读要新 session；批量用 bulk；action 要大写

---

## 🚨 最常见的 5 个坑

### 1. Session 未关闭 → 连接池耗尽

```python
# ❌ 错误
def bad():
    session = get_db_session()
    result = session.query(Stock).all()
    return result  # session 泄漏！

# ✅ 正确
def good():
    with get_db_session() as session:
        result = session.query(Stock).all()
    return result  # session 自动关闭
```

**症状**: `too many clients already`

---

### 2. 写后读在同一个 with 块 → 读不到数据

```python
# ❌ 错误
def bad():
    with get_db_session() as session:
        session.add(Stock(symbol='600000.SH'))
        session.commit()
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
    return result  # 可能读不到！

# ✅ 正确
def good():
    # 写
    with get_db_session() as session:
        session.add(Stock(symbol='600000.SH'))
        session.commit()
    
    # 读（新 session）
    with get_db_session() as session:
        result = session.query(Stock).filter_by(symbol='600000.SH').first()
    return result
```

**关键**: 写完必须关闭 session，再开新 session 读

---

### 3. 循环插入 → 性能极差

```python
# ❌ 错误（1000 条 = 30 秒）
def bad(klines: List[Dict]):
    for kline in klines:
        session.add(Kline(**kline))
        session.commit()  # 每次都 commit！

# ✅ 正确（1000 条 = 0.5 秒）
def good(klines: List[Dict]):
    session.bulk_insert_mappings(Kline, klines)
    session.commit()  # 一次 commit
```

**加速 60 倍**: 用 `bulk_insert_mappings`

---

### 4. Action 大小写不统一 → 数据不匹配

```python
# ❌ 错误
trade_data = {'action': 'sell'}  # 小写
session.query(Trade).filter_by(action='SELL')  # 大写查询，查不到！

# ✅ 正确
def normalize_action(action: str) -> str:
    return action.upper() if action else action

trade_data = {'action': normalize_action('sell')}  # 'SELL'
session.query(Trade).filter_by(action='SELL')  # 匹配
```

**后果**: 幽灵持仓、估值错误

---

### 5. Session 跨线程共享 → 崩溃

```python
# ❌ 错误
global_session = get_db_session()  # 全局 session

def thread_worker():
    result = global_session.query(Stock).all()  # 多线程共享，崩溃！

# ✅ 正确
def thread_worker():
    with get_db_session() as session:  # 每个线程独立 session
        result = session.query(Stock).all()
```

**原则**: Session 不是线程安全的

---

## 📋 Repository 模式规范

### 返回类型

```python
# ✅ 返回字典
def get_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
    row = self.session.query(Stock).filter_by(symbol=symbol).first()
    if row:
        return {'symbol': row.symbol, 'name': row.name}
    return None

# ❌ 返回 ORM 对象（session 关闭后无法访问）
def get_by_symbol(self, symbol: str) -> Stock:
    return self.session.query(Stock).filter_by(symbol=symbol).first()
```

### 异常处理

```python
# ✅ 正确
try:
    session.add(stock)
    session.commit()
    return stock.id
except IntegrityError:
    session.rollback()  # ✅ 回滚
    logger.error("Duplicate key")
    return None

# ❌ 错误（不回滚，session 进入脏状态）
session.add(stock)
session.commit()  # 可能失败但不处理
```

---

## 🔥 FastAPI 专项

### 依赖注入

```python
from fastapi import Depends

# ✅ 正确
@app.get("/stocks/{symbol}")
def get_stock(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter_by(symbol=symbol).first()
    return stock

# ❌ 错误（手动管理，中间件无法清理）
@app.get("/stocks/{symbol}")
def get_stock(symbol: str):
    with get_db_session() as session:
        stock = session.query(Stock).filter_by(symbol=symbol).first()
    return stock
```

### 后台任务

```python
from fastapi import BackgroundTasks

# ✅ 正确
@app.post("/klines/update")
def update_klines(symbol: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_klines, symbol)
    return {"status": "processing"}

# ❌ 错误（占用连接太久）
@app.post("/klines/update")
def update_klines(symbol: str, db: Session = Depends(get_db)):
    for i in range(10000):  # 几分钟
        db.add(Kline(...))
    db.commit()  # 连接占用太久！
```

---

## 🎯 性能优化

### Eager Loading（避免 N+1）

```python
from sqlalchemy.orm import joinedload

# ❌ N+1 查询（1000 条 = 1001 次查询）
stocks = session.query(Stock).all()
for stock in stocks:
    print(stock.klines)  # 每次都查询数据库

# ✅ Eager loading（1000 条 = 1 次查询）
stocks = session.query(Stock).options(joinedload(Stock.klines)).all()
for stock in stocks:
    print(stock.klines)  # 已加载到内存
```

### 批量操作

```python
# ✅ bulk_insert_mappings（最快）
session.bulk_insert_mappings(Kline, klines)
session.commit()

# ✅ bulk INSERT（次快）
from sqlalchemy import insert
stmt = insert(Kline).values(klines)
session.execute(stmt)
session.commit()

# ❌ 循环 add（最慢）
for kline in klines:
    session.add(Kline(**kline))
session.commit()
```

---

## 🔍 常见 Bug 症状速查

| 症状 | 根因 | 解决 |
|------|------|------|
| `too many clients` | Session 泄漏 | 用 `with get_db_session()` |
| `DetachedInstanceError` | Session 关闭后访问关联对象 | 用 `joinedload` 预加载 |
| 写入后查不到 | 写后读在同一 with 块 | 写完关 session，读开新 session |
| 幽灵持仓 | action 大小写不匹配 | 统一大写 `normalize_action()` |
| FastAPI 500 超时 | Session 池耗尽 | 用 `Depends(get_db)` |
| 插入很慢 | 循环 commit | 改用 `bulk_insert_mappings` |

---

## ✅ Code Review 检查清单

提交前确认：

- [ ] 所有 session 都用 `with get_db_session()`
- [ ] 写后读分离（不在同一 with 块）
- [ ] 批量操作用 bulk 方法
- [ ] action/status 等枚举值统一大写
- [ ] 异常捕获后有 `rollback()`
- [ ] FastAPI 用 `Depends(get_db)`
- [ ] 长任务用 `BackgroundTasks`
- [ ] 关联查询用 `joinedload`

---

## 📚 完整文档

详细规范请参考: [FRAMEWORK_CONSTRAINTS.md](FRAMEWORK_CONSTRAINTS.md)

---

**快速诊断**: 
- 连接池满 → 检查 session 是否关闭
- 读不到数据 → 检查是否写后读分离
- 性能慢 → 检查是否用 bulk 操作
- 数据不匹配 → 检查枚举值大小写
