# BaseRepository 迁移实施计划（legacy → db_cursor 上下文管理器）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消灭 legacy `BaseRepository`（`infrastructure/persistence/database/base_repository.py`，实例级持有连接的泄漏源），全部用法迁到 per-operation `db_cursor()` 上下文管理器，保持 dict 契约逐字不变，最终删除该文件。

**Architecture:** 在 `engine.py` 新增唯一基建 `db_cursor(commit=False)` contextmanager（~35 行，复用 `engine.connect()` + 底层 psycopg2 conn + RealDictCursor，与旧 BaseRepository 同路径但用完立即归还池）。校验方法抽为纯函数 `validators.py`。两个 Repository 子类只改内部实现（SQL、签名、返回类型不动），去掉 BaseRepository 继承。直插用法（session_service 等）机械改写。调用方（10+ 处 `StockPoolORMRepository()` 实例化）**零改动**——迁移后实例不再持连接，单例无害。

**Tech Stack:** Python 3.13 / SQLAlchemy 2.x QueuePool / psycopg2（源码编译，禁 binary）/ pytest / FastAPI 5001

**历史教训（必须敬畏）:** 2026-08-04 commit 8f06ae1 曾尝试把这批 repo 迁到 ORM，系统性破坏契约（删方法、返回类型漂移），被迫整体恢复。本次是**第三次触碰**这些文件。铁律：**只换连接获取方式，其他逐字不动**。

---

## 通用规则块（所有执行 agent 必读，违反即返工）

1. **Worktree 隔离**：每个 WP 一个独立 worktree。开工先 `git branch --show-current` 确认；不符即停手报告。禁止在共享主工作区直接提交。
2. **禁止批量覆盖**：不执行 `git checkout <ref> -- .`、`git restore --source=<ref> .`。`git status` 出现不属于自己的改动 = 停手信号，只 add 本 WP 的文件。
3. **工作目录**：仓库根是 `/Users/yunpeng/pi-investment`，代码在 `quantsys-v2/` 子目录。worktree 路径 `.claude/worktrees/<wp-name>/quantsys-v2`。所有 pytest 必须从 quantsys-v2 目录运行，解释器用 `venv/bin/python`（相对 quantsys-v2）。
4. **基线先行**：改任何代码前先记录测试基线（WP-0）。评判标准 = **不允许出现新增失败**，预存在失败不算回归（参考记忆 baseline-failing-tests）。
5. **测试库安全**：pytest 下数据库名必须以 `_test` 结尾（conftest 强制）。严禁对 `quant_investment` 生产库跑测试。
6. **端口固定**：5001 FastAPI 生产（launchd）、5099 测试实例。worktree 内测试若改端口，合并前必须改回。
7. **禁止 psycopg2-binary**（双 OpenSSL 崩溃），禁止动 `requirements*`。
8. **契约红线**：方法签名、返回类型、SQL 语句、参数顺序、错误消息文案，逐字保持。迁移前后用 grep 快照 diff 证明（各 WP 内有具体命令）。
9. **真跑验证**：每个 WP 合并前必须真跑相关 pytest 文件并粘贴结果；禁止"应该能过"。
10. **合并回 main**（merge-back 流程，已在 7dddb54/a9d5f6a/be2d2d3 三次验证）：
    - worktree 内完成提交 → rebase 到本地 main 最新
    - 确认 `git rev-parse main` 基点未被其他会话移动
    - `git update-ref refs/heads/main <worktree-HEAD>`
    - 用 `cp` 把本 WP 改动的文件从 worktree 覆盖到主工作区对应路径（`&&` 链式，禁止变量循环复合命令——钩子会拒绝）
    - 主工作区 `git add` 本 WP 文件
    - ExitWorktree（remove）
11. **部署**：只有 WP-6 涉及生产部署。重启命令 `launchctl kickstart -k gui/501/com.pi-investment.v2-api`，日志 `~/v2-api.log`（不是 logs/ 下任何文件）。
12. **日报**：每个 WP 结束输出：改动文件清单 / 测试前后对比 / 契约 diff 结果 / 遗留问题。

---

## 背景：问题与目标模式

**现状问题**：`BaseRepository.__init__` 立即 `engine.connect()` 并把连接存 `self.db`，实例活多久连接占多久。单例服务（`adapters/shared/services.py:18` 模块级 `pool_repo` 等 10+ 处）每个永久占 1 条池连接。2026-08-18 连接池耗尽事故（见记忆 fastapi-orm-session-pool-exhaustion）后，ORM 侧已修好，legacy 侧是残留的有界泄漏。

**目标模式**（每次操作用完即归还）：

```python
from infrastructure.persistence.database.engine import db_cursor

# 读
with db_cursor() as cursor:
    cursor.execute("SELECT ...", (arg,))
    rows = cursor.fetchall()   # RealDictRow，dict 子类

# 写（commit/rollback 由 helper 负责）
with db_cursor(commit=True) as cursor:
    cursor.execute("UPDATE ...", (arg,))
```

**语义要点**（ executor 必须理解）：
- psycopg2 默认事务模式，SELECT 也开事务；helper 非 commit 模式退出时显式 `rollback()` 再归还，杜绝 `idle in transaction` 残影。
- `conn.connection` 取底层 psycopg2 conn 直接操作——与旧 BaseRepository 完全相同的路径（生产验证过的语义），SQLAlchemy 只负责池管理。
- 行类型仍是 `RealDictRow`（dict 子类），`dict(row)` 行为不变。

**Legacy BaseRepository 全部用法清单**（2026-08-18 盘点，执行时须重新 grep 确认）：

| 用法 | 位置 | 迁移 WP |
|---|---|---|
| `StockPoolRepository(BaseRepository)` + alias `StockPoolORMRepository` | `adapters/outbound/repositories/stock_pool_repository.py:46` | WP-2 |
| `StrategyPerformanceRepository(BaseRepository)` | `adapters/outbound/repositories/strategy_performance_repository.py:17` | WP-3 |
| `BaseRepository()` ×6（session 持久化） | `application/services/session_service.py:34,90,105,113,131,190` | WP-4 |
| `BaseRepository()`（trading calendar 加载） | `application/services/data_pipeline_service.py:32` | WP-4 |
| `BaseRepository()`（/api/agent/logs） | `adapters/inbound/fastapi_app/routes/signals_async.py:471` | WP-4 |
| `BaseRepository()`（Flask 同款 /api/agent/logs） | `adapters/inbound/api/routes/signals.py:703` | WP-4 |
| `BaseRepository.__new__` 只借 `_validate_symbol` | `application/services/trade_service.py:21,202` | WP-4 |
| `_resolve_db_dsn` 外部依赖 ×2 | `conftest.py:75`、`tools/validate_wp15.py:128` | WP-5 |
| 测试直接用 `BaseRepository()` 当查询工具 ×4 | `tests/api/test_agent_session_routes.py:10`、`tests/services/test_ai_diagnosis.py:12`、`tests/migration/test_agent_sessions_parity.py:32`、`tests/services/test_session_service.py:26` | WP-4 |
| `tests/test_base_repository.py` | 整文件 | WP-5 删除 |

注：`adapters/inbound/api/shared.py:77` 和 `adapters/shared/services.py:18` 的模块级 `pool_repo = StockPoolORMRepository()` **不需要改**——WP-2 后实例不再持连接。`init_connection_pool`/`close_connection_pool` 无外部调用方。

---

## WP 总览 / LMH 分级 / 并行轨道

| WP | 内容 | 风险 | 建议模型 | 依赖 | 轨道 |
|---|---|---|---|---|---|
| WP-0 | 基线快照（测试 + 契约 grep） | L | Haiku | 无 | 先行 |
| WP-1 | 基建：`db_cursor()` + `validators.py` | M | Sonnet | WP-0 | 先行 |
| WP-2 | StockPoolRepository 迁移 | **H** | Sonnet（禁 Haiku） | WP-1 | 轨道 A |
| WP-3 | StrategyPerformanceRepository 迁移 | M | Sonnet | WP-1 | 轨道 B（∥A） |
| WP-4 | 直插用法 + 4 测试文件改写 | M | Sonnet | WP-1 | 轨道 C（∥A∥B） |
| WP-5 | 删除 base_repository.py + `_resolve_db_dsn` 搬家 + 全量回归 | M | Sonnet | WP-2+3+4 全合并 | 汇合 |
| WP-6 | 生产部署 + 验证 | L | Haiku/Sonnet | WP-5 | 收尾 |

**文件不重叠证明**：WP-2 只碰 `stock_pool_repository.py`；WP-3 只碰 `strategy_performance_repository.py`；WP-4 碰 services/routes/tests（不动两个 repository 文件）；WP-1 碰 `engine.py` + 新建 `validators.py`。三轨道可安全并行，各自 worktree。

**Claude 终审节点**：WP-1 合并前、WP-2 合并前（重点）、WP-5 合并前，各 WP 的 diff 必须先经 Claude 审查通过再 merge-back。

---

## WP-0：基线快照（L）

**Files:**
- 无代码改动，只产出 `/tmp/base-repo-migration-baseline.md`

- [ ] **Step 1: 确认工作区状态**

```bash
cd /Users/yunpeng/pi-investment && git branch --show-current && git rev-parse main
```
Expected: `main`，记录 commit hash。

- [ ] **Step 2: 跑基线测试并记录结果**

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_stock_pool_repository.py tests/test_strategy_performance_repository.py tests/services/test_session_service.py tests/api/test_agent_session_routes.py tests/services/test_ai_diagnosis.py tests/migration/test_agent_sessions_parity.py tests/test_base_repository.py tests/test_order_pnl_tracking.py tests/test_performance_api.py tests/test_experience_accumulator.py -q 2>&1 | tail -20
```
把 pass/fail 数字与失败用例名原文记录到基线文件。已知预存在失败：`tests/test_base_repository.py` 有 2 个（test_validate_symbol_wrong_length、test_get_cursor_triggers_lazy_connection）。

- [ ] **Step 3: 契约快照（两个 repository 的完整方法签名）**

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2 && grep -n "    def \|^class " adapters/outbound/repositories/stock_pool_repository.py > /tmp/contract_stock_pool_before.txt && grep -n "    def \|^class " adapters/outbound/repositories/strategy_performance_repository.py > /tmp/contract_strategy_perf_before.txt && cat /tmp/contract_stock_pool_before.txt /tmp/contract_strategy_perf_before.txt
```

- [ ] **Step 4: 用法清单复核（与上表对账）**

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2 && grep -rn "BaseRepository\|base_repository" --include="*.py" . | grep -v "/venv/\|/tests/test_base_repository\|async_base_repository" | sort
```
若出现上表之外的新用法，**停手报告**，由 Claude 更新计划。

- [ ] **Step 5: 输出基线文件**（含 main hash、测试数字、契约快照路径、用法清单 diff 结论）

---

## WP-1：基建 db_cursor + validators（M）

**Files:**
- Modify: `infrastructure/persistence/database/engine.py`（文件尾追加）
- Create: `infrastructure/persistence/database/validators.py`
- Test: `tests/infrastructure/test_db_cursor.py`（新建）

- [ ] **Step 1: 建 worktree `wp1-db-cursor`，确认基于最新 main**

- [ ] **Step 2: 写失败测试 `tests/infrastructure/test_db_cursor.py`**

```python
"""db_cursor 与 validators 基建测试。"""
import pytest


class TestDbCursor:
    def test_read_returns_dict_rows(self):
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
            cursor.execute("SELECT 1 AS one")
            row = cursor.fetchone()
        assert isinstance(row, dict)
        assert row["one"] == 1

    def test_write_commits_when_commit_true(self):
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                "CREATE TEMP TABLE t_db_cursor_wp1 (id int)"
            )
        # TEMP TABLE 随连接归池 rollback 消失属正常；此处只验证不抛异常

    def test_exception_rolls_back_and_reraises(self):
        from infrastructure.persistence.database.engine import db_cursor
        with pytest.raises(Exception, match="boom_wp1"):
            with db_cursor(commit=True) as cursor:
                raise Exception("boom_wp1")

    def test_connection_returned_to_pool(self):
        """连续获取超过 pool_size 次数不阻塞 = 连接确实归还。"""
        from infrastructure.persistence.database.engine import db_cursor
        for _ in range(15):
            with db_cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()


class TestValidators:
    def test_validate_symbol_accepts_plain(self):
        from infrastructure.persistence.database.validators import validate_symbol
        assert validate_symbol("600519") is True

    def test_validate_symbol_accepts_suffix(self):
        from infrastructure.persistence.database.validators import validate_symbol
        assert validate_symbol("600519.SH") is True
        assert validate_symbol("000001.sz") is True

    def test_validate_symbol_rejects_empty(self):
        from infrastructure.persistence.database.validators import validate_symbol
        with pytest.raises(ValueError, match="股票代码不能为空"):
            validate_symbol("")

    def test_validate_symbol_rejects_bad_format(self):
        from infrastructure.persistence.database.validators import validate_symbol
        with pytest.raises(ValueError, match="股票代码格式错误"):
            validate_symbol("ABC123")

    def test_validate_date(self):
        from infrastructure.persistence.database.validators import validate_date
        assert validate_date("2026-08-18") is True
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date("2026/08/18")

    def test_validate_positive_number(self):
        from infrastructure.persistence.database.validators import validate_positive_number
        assert validate_positive_number(1.5, "price") is True
        with pytest.raises(ValueError, match="must be positive"):
            validate_positive_number(0, "price")
```

- [ ] **Step 3: 跑测试确认失败（模块不存在）**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/infrastructure/test_db_cursor.py -q 2>&1 | tail -5
```
Expected: FAIL（ImportError）

- [ ] **Step 4: 实现 `engine.py` 追加（文件尾）**

```python
# ==================== db_cursor: per-operation 游标（替代 legacy BaseRepository） ====================

from contextlib import contextmanager


@contextmanager
def db_cursor(commit: bool = False):
    """单次操作级数据库游标（RealDictCursor），with 块结束立即归还连接池。

    替代 legacy BaseRepository 的实例级持连接模式。
    - commit=False（默认，读操作）：退出时显式 rollback（psycopg2 默认事务模式，
      SELECT 也开事务，不 rollback 归还会留 idle-in-transaction 残影）
    - commit=True（写操作）：正常退出 commit；异常 rollback 并重抛

    行类型为 psycopg2 RealDictRow（dict 子类），与旧 BaseRepository 完全一致。
    """
    from psycopg2.extras import RealDictCursor

    conn = get_engine().connect()
    try:
        raw = conn.connection  # 底层 psycopg2 connection（与旧 BaseRepository 同路径）
        cursor = raw.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                raw.commit()
            else:
                raw.rollback()
        except Exception:
            raw.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conn.close()
```

- [ ] **Step 5: 实现 `validators.py`（从 base_repository.py 逐字抽出，实例方法改纯函数，逻辑/文案一字不改）**

```python
"""纯函数校验器（自 legacy BaseRepository 抽出，无 DB 依赖）。

错误消息文案与 legacy BaseRepository._validate_* 逐字一致——
调用方（含 agent 工具层）可能匹配这些文案。
"""
from datetime import datetime


def validate_symbol(symbol: str) -> bool:
    if not symbol:
        raise ValueError("股票代码不能为空")
    if not isinstance(symbol, str):
        raise ValueError("股票代码必须是字符串")

    base = symbol.strip().upper()
    for suffix in (".SZ", ".SH", ".HK"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    if not base.isdigit() or not (4 <= len(base) <= 6):
        raise ValueError(f"股票代码格式错误: {symbol}")
    return True


def validate_date(date_str: str) -> bool:
    if not date_str:
        raise ValueError("Date cannot be empty")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")


def validate_positive_number(value: float, name: str) -> bool:
    if value is None:
        raise ValueError(f"{name} cannot be None")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return True
```

- [ ] **Step 6: 跑测试确认全过**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/infrastructure/test_db_cursor.py -q 2>&1 | tail -3
```
Expected: 11 passed

- [ ] **Step 7: 全量基线对比（不允许新增失败）**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/repositories/ tests/services/test_session_service.py -q 2>&1 | tail -3
```
与 WP-0 基线对比。

- [ ] **Step 8: 提交 + Claude 终审 diff + merge-back（通用规则 10）**

**验收检查清单：**
- [ ] `db_cursor` 读路径退出时 rollback（看代码确认，不是"应该"）
- [ ] validators 三个函数错误文案与 base_repository.py 原文逐字一致（diff 检查）
- [ ] 11 个新测试全过，基线无新增失败

---

## WP-2：StockPoolRepository 迁移（H，禁 Haiku）

**Files:**
- Modify: `adapters/outbound/repositories/stock_pool_repository.py`（唯一改动文件）

**契约表（迁移前后必须逐字一致，来自 WP-0 快照）：**

```
class StockPool(Base)                      # ORM 模型类，不动
class StockPoolRepository(BaseRepository)  # → 改为 (object)，类名不变
    create(data: Dict) -> Dict
    get_by_id(pool_id: int) -> Optional[Dict]
    get_pool(pool_id: int) -> Optional[Dict]      # get_by_id 的 alias，16 个生产调用方，禁删
    get_all() -> List[Dict]
    get_dynamic_pools() -> List[Dict]
    update(pool_id: int, data: Dict) -> Optional[Dict]
    update_symbols(pool_id: int, symbols: List[str]) -> Optional[Dict]
    update_validation(pool_id: int, validation: Dict) -> Optional[Dict]
    delete(pool_id: int) -> bool
    update_scan_enabled(pool_id: int, enabled: bool) -> bool
    update_signal_scan(pool_id: int, scan_result: Dict) -> Optional[Dict]
    _parse_row(row) -> Dict                         # JSONB/ARRAY 解析逻辑，逐字保留
```

- [ ] **Step 1: 建 worktree `wp2-stock-pool-repo`，rebase 到含 WP-1 的最新 main**

- [ ] **Step 2: 契约快照**

```bash
cd <worktree>/quantsys-v2 && grep -n "    def \|^class " adapters/outbound/repositories/stock_pool_repository.py > /tmp/contract_wp2_before.txt && diff /tmp/contract_stock_pool_before.txt /tmp/contract_wp2_before.txt
```
Expected: 无 diff（若 WP-0 后有其他会话动过此文件，停手报告）。

- [ ] **Step 3: 基线测试**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_stock_pool_repository.py tests/repositories/test_agent_intelligence_repository.py -q 2>&1 | tail -3
```
记录数字。

- [ ] **Step 4: 改造 `__init__` 与类声明**

- `class StockPoolRepository(BaseRepository)` → `class StockPoolRepository:`（移除 import 中的 BaseRepository）
- 删除继承来的 eager connect。若类内无自定义 `__init__`，新增：

```python
    def __init__(self, db_connection=None):
        """db_connection 参数仅为向后兼容保留（忽略）。连接按操作现取现还。"""
        pass

    def close(self):
        """兼容旧调用方的 no-op（连接不再由实例持有）。"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
```

- [ ] **Step 5: 逐方法机械改写（12 个方法）**

改写模板——**SQL 字符串、参数、`_parse_row` 调用、返回语句逐字不动**，只换游标获取与提交：

改写前形态：
```python
    def get_by_id(self, pool_id: int) -> Optional[Dict]:
        cursor = self._get_cursor()
        try:
            cursor.execute("SELECT ... WHERE id = %s", (pool_id,))
            row = cursor.fetchone()
            return self._parse_row(row) if row else None
        finally:
            cursor.close()
```

改写后：
```python
    def get_by_id(self, pool_id: int) -> Optional[Dict]:
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
            cursor.execute("SELECT ... WHERE id = %s", (pool_id,))
            row = cursor.fetchone()
            return self._parse_row(row) if row else None
```

写方法（含 `self.db.commit()` 的：create / update / update_symbols / update_validation / delete / update_scan_enabled / update_signal_scan）：
```python
        with db_cursor(commit=True) as cursor:
            # 原 try 体内全部 SQL 原样搬入；删去 self.db.commit() / self.db.rollback()
```

规则：
- import 放方法内（与现有代码风格一致，避免循环 import 风险）
- 原方法体内若有多次 execute 再一次 commit，全部放进同一个 `with db_cursor(commit=True)` 块
- 原代码异常路径若无显式 rollback，helper 会自动 rollback——语义等价（原来靠连接归池 rollback），不需补
- 类内对 `_validate_symbol` 等校验方法的调用（若有）改为 `from infrastructure.persistence.database.validators import validate_symbol` 模块内顶部 import + 函数调用
- **禁止**保留 `_get_cursor`/`cursor()`/`_get_db`/`_get_connection` 任何痕迹

- [ ] **Step 6: 改写后契约 diff（必须只剩继承行变化）**

```bash
cd <worktree>/quantsys-v2 && grep -n "    def \|^class " adapters/outbound/repositories/stock_pool_repository.py > /tmp/contract_wp2_after.txt && diff /tmp/contract_wp2_before.txt /tmp/contract_wp2_after.txt
```
Expected diff：仅 `class StockPoolRepository(BaseRepository)` → `class StockPoolRepository:`，加上新增的 `__init__`/`close`/`__enter__`/`__exit__` 四行。方法名、参数、顺序零变化。

- [ ] **Step 7: 残留检查**

```bash
cd <worktree>/quantsys-v2 && grep -n "self\.db\|_get_cursor\|_get_connection\|BaseRepository" adapters/outbound/repositories/stock_pool_repository.py
```
Expected: 零输出。

- [ ] **Step 8: 跑契约测试 + 相关测试**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/repositories/test_stock_pool_repository.py tests/repositories/test_agent_intelligence_repository.py -q 2>&1 | tail -3 && venv/bin/python -m pytest tests/services/ -q -k "pool or scan" 2>&1 | tail -3
```
与 Step 3 基线对比，不允许新增失败。

- [ ] **Step 9: 验证 alias 与调用方不受影响**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -c "
from adapters.outbound.repositories import StockPoolORMRepository
r = StockPoolORMRepository()
pools = r.get_all()
print('pools:', len(pools), 'type:', type(pools[0]) if pools else 'empty')
print('alias ok, keys sample:', sorted(pools[0].keys())[:8] if pools else '-')
"
```
Expected: 正常返回 dict 列表（测试库）。

- [ ] **Step 10: 提交 → Claude 终审（重点审：SQL 逐字未动、_parse_row 未动、契约 diff）→ merge-back**

**验收检查清单：**
- [ ] 契约 diff 只剩类声明行 + 4 个兼容方法
- [ ] `git diff` 中所有 SQL 字符串行无 `+`/`-` 变化（除缩进）
- [ ] 测试基线无新增失败
- [ ] 10+ 处调用方文件零改动

---

## WP-3：StrategyPerformanceRepository 迁移（M）

**Files:**
- Modify: `adapters/outbound/repositories/strategy_performance_repository.py`（唯一改动文件）

方法与 WP-2 完全同构。契约表（以 WP-0 快照 `/tmp/contract_strategy_perf_before.txt` 为准）：`create / update_exit / get_by_strategy_and_symbol / get_recent / get_by_scenario_tag / get_statistics`（完整签名见源文件，executor 开工先 grep 快照，禁止凭本计划记忆签名）。

- [ ] **Step 1: 建 worktree `wp3-strategy-perf-repo`，rebase 到含 WP-1 的最新 main**
- [ ] **Step 2: 契约快照 + 与 WP-0 对账**（同 WP-2 Step 2，文件名换 strategy_performance）
- [ ] **Step 3: 基线测试**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/test_strategy_performance_repository.py tests/test_order_pnl_tracking.py tests/test_performance_api.py tests/test_experience_accumulator.py -q 2>&1 | tail -3
```

- [ ] **Step 4: 类声明去 BaseRepository 继承 + 加兼容四方法**（同 WP-2 Step 4；注意该类已有自定义 `__init__`（line 20），改为不再调 `super().__init__()`，保留 `db_connection=None` 形参并忽略）
- [ ] **Step 5: 逐方法机械改写**（同 WP-2 Step 5 模板；写方法 = create / update_exit，读方法 = 其余）
- [ ] **Step 6-7: 契约 diff + 残留检查**（同 WP-2）
- [ ] **Step 8: 测试对比**（同 Step 3 命令，不允许新增失败）
- [ ] **Step 9: 提交 → merge-back**（M 级，Claude 抽查 diff 即可）

**验收检查清单：** 同 WP-2 清单（替换文件名）。

---

## WP-4：直插用法 + 测试改写（M）

**Files:**
- Modify: `application/services/session_service.py`（6 处）
- Modify: `application/services/data_pipeline_service.py`（1 处）
- Modify: `adapters/inbound/fastapi_app/routes/signals_async.py`（1 处，line ~461-472）
- Modify: `adapters/inbound/api/routes/signals.py`（1 处，line ~692-703，Flask 回滚栈同款函数）
- Modify: `application/services/trade_service.py`（2 行：line 11 import、line 20-21、line 202 调用）
- Modify: `tests/api/test_agent_session_routes.py`、`tests/services/test_ai_diagnosis.py`、`tests/migration/test_agent_sessions_parity.py`、`tests/services/test_session_service.py`（各 1 处 `BaseRepository()` 查询工具用法）

- [ ] **Step 1: 建 worktree `wp4-direct-usages`，rebase 到含 WP-1 的最新 main**

- [ ] **Step 2: 基线测试**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/services/test_session_service.py tests/api/test_agent_session_routes.py tests/services/test_ai_diagnosis.py tests/migration/test_agent_sessions_parity.py tests/test_order_trade.py -q 2>&1 | tail -3
```

- [ ] **Step 3: session_service.py 改写 6 处**

每处形态（读）：
```python
        repo = BaseRepository()
        cursor = repo._get_cursor()
        try:
            cursor.execute(...)
            ...
        finally:
            cursor.close()
```
→
```python
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
            cursor.execute(...)
            ...
```

写路径（含 `repo.db.commit()`，line 86 与 line 220 区域）：整段搬入 `with db_cursor(commit=True) as cursor:`，删 `repo.db.commit()`。line 168 区域的 `repo.db.rollback()` 删除（helper 异常自动 rollback）。文件顶部 `from infrastructure.persistence.database.base_repository import BaseRepository`（line 10）删除。**SQL 与业务逻辑逐字不动。**

- [ ] **Step 4: data_pipeline_service.py 改写**

原形态（line 30-45 区域）：`repo = BaseRepository()` → `if not repo.db:` 健康检查 → `repo.cursor()` 查询。
改为：
```python
    from infrastructure.persistence.database.engine import db_cursor
    try:
        with db_cursor() as cursor:
            cursor.execute(
                """
                SELECT trade_date
                FROM quant.trading_calendar
                WHERE exchange = %s AND is_trading_day = TRUE
                """,
                (exchange,),
            )
            # 原 fetchall 与集合构造逻辑逐字保留
    except Exception:
        logger.warning("Database connection not available. Using empty calendar.")
        return set()
```
（executor 先读原函数完整实现，返回类型 `Set[date]` 契约不变；上面 SQL 是从源文件抄的，改写时以源文件原文为准。）

- [ ] **Step 5: signals_async.py 与 api/routes/signals.py 的 get_agent_logs 改写（两处同构）**

`repo = BaseRepository()` + `repo._get_cursor()` → `with db_cursor() as cursor:`。查询逻辑（COUNT + 分页 SELECT）逐字不动。注意 signals_async.py 里 cursor 用完是否有 finally close——有则随 try/finally 一起删。函数尾部若引用 `repo` 则一并清理。

- [ ] **Step 6: trade_service.py 改写**

```python
# 删除 line 11: from infrastructure.persistence.database.base_repository import BaseRepository
# 删除 line 20-21: # 复用 BaseRepository 的校验方法 / _validator = BaseRepository.__new__(BaseRepository)
# 替换为:
from infrastructure.persistence.database.validators import validate_symbol
# line 202: _validator._validate_symbol(symbol) → validate_symbol(symbol)
```

- [ ] **Step 7: 4 个测试文件改写**

每个文件中 `repo = BaseRepository()` + `repo._get_cursor()`（或 `repo.cursor()`）的夹具查询改为 `with db_cursor() as cursor:`。先读每个文件的实际用法再改；只改 BaseRepository 相关行。

- [ ] **Step 8: 残留检查**

```bash
cd <worktree>/quantsys-v2 && grep -rn "BaseRepository" application/services/session_service.py application/services/data_pipeline_service.py application/services/trade_service.py adapters/inbound/fastapi_app/routes/signals_async.py adapters/inbound/api/routes/signals.py tests/api/test_agent_session_routes.py tests/services/test_ai_diagnosis.py tests/migration/test_agent_sessions_parity.py tests/services/test_session_service.py
```
Expected: 零输出。

- [ ] **Step 9: 测试对比（Step 2 命令重跑 + trade 相关）**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/services/test_session_service.py tests/api/test_agent_session_routes.py tests/services/test_ai_diagnosis.py tests/migration/test_agent_sessions_parity.py tests/test_order_trade.py -q 2>&1 | tail -3
```

- [ ] **Step 10: 提交 → merge-back**

**验收检查清单：**
- [ ] 9 个文件 BaseRepository 残留为零
- [ ] SQL 语句零改动（diff 中 SQL 行只有缩进变化）
- [ ] 测试基线无新增失败
- [ ] trade_service 的 symbol 校验错误文案不变（`股票代码格式错误`）

---

## WP-5：删除 base_repository.py + 全量回归（M）

**前置**：WP-2/3/4 全部合并到 main。

**Files:**
- Modify: `infrastructure/persistence/database/engine.py`（搬入 `_resolve_db_dsn` + `TEST_DB_SUFFIX`）
- Modify: `conftest.py:75`、`tools/validate_wp15.py:128`（import 路径改指 engine）
- Delete: `infrastructure/persistence/database/base_repository.py`
- Delete: `tests/test_base_repository.py`

- [ ] **Step 1: 建 worktree `wp5-delete-legacy`，rebase 最新 main**
- [ ] **Step 2: 全局引用复核**

```bash
cd <worktree>/quantsys-v2 && grep -rn "base_repository\|BaseRepository" --include="*.py" . | grep -v "/venv/\|async_base_repository\|orm/base_repository"
```
Expected: 仅剩 `base_repository.py` 自身、`tests/test_base_repository.py`、`conftest.py`、`tools/validate_wp15.py`。出现其他文件 = 停手报告（有遗漏用法）。
注意：`infrastructure/persistence/orm/base_repository.py`（ORM 版 BaseORMRepository）和 `async_base_repository.py` **不在删除范围**，禁止误伤。

- [ ] **Step 3: `_resolve_db_dsn` + `TEST_DB_SUFFIX` 逐字搬到 engine.py**（含 pytest 安全检查全部逻辑与注释；`__all__` 相应更新）

- [ ] **Step 4: 改 conftest.py:75 与 tools/validate_wp15.py:128 的 import 为 `from infrastructure.persistence.database.engine import _resolve_db_dsn`**

- [ ] **Step 5: 删除两个文件**

```bash
cd <worktree>/quantsys-v2 && git rm infrastructure/persistence/database/base_repository.py tests/test_base_repository.py
```

- [ ] **Step 6: 全量回归**

```bash
cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/ -q --ignore=tests/e2e 2>&1 | tail -5
```
与 WP-0 全量基线对比（注意：基线里 test_base_repository 的 2 个预存在失败随文件删除消失，属预期）。

- [ ] **Step 7: 冷启动冒烟（证明 committed 状态可启动——a9d5f6a 教训）**

```bash
cd <worktree>/quantsys-v2 && USE_AGENT_OS_SCHEDULER=false PORT=5099 venv/bin/python -m uvicorn adapters.inbound.fastapi_app.main:app --host 127.0.0.1 --port 5099 &
sleep 8 && curl -s http://127.0.0.1:5099/api/health/db | head -c 300 && curl -s "http://127.0.0.1:5099/api/pools" | head -c 200 && curl -s "http://127.0.0.1:5099/api/agent/logs?page=1&page_size=5" | head -c 200 && kill %1
```
Expected: 三个端点均 200 非错误体。

- [ ] **Step 8: 提交 → Claude 终审 → merge-back**

**验收检查清单：**
- [ ] 全局 grep 零 legacy 引用
- [ ] `_resolve_db_dsn` 的 pytest 安全检查逐字保留（生产库保护不能丢）
- [ ] 全量回归无新增失败
- [ ] 5099 冷启动三端点冒烟通过

---

## WP-6：生产部署验证（L）

- [ ] **Step 1: 主工作区确认 main 含全部 WP，工作区干净**

```bash
cd /Users/yunpeng/pi-investment && git log main --oneline -8 && git status --short | head
```

- [ ] **Step 2: push + 重启生产**

```bash
cd /Users/yunpeng/pi-investment && git push origin main && launchctl kickstart -k gui/501/com.pi-investment.v2-api && sleep 12
```

- [ ] **Step 3: 生产冒烟（覆盖全部迁移面的端点）**

```bash
curl -s http://127.0.0.1:5001/api/health/db | head -c 300; echo; curl -s "http://127.0.0.1:5001/api/pools" | head -c 200; echo; curl -s "http://127.0.0.1:5001/api/signals/statistics" | head -c 200; echo; curl -s "http://127.0.0.1:5001/api/agent/logs?page=1&page_size=5" | head -c 200
```
Expected: 全部 200。

- [ ] **Step 4: 连接状态验证（核心指标）**

```bash
psql "$QUANT_DATABASE_URL" -c "SELECT state, count(*) FROM pg_stat_activity WHERE datname='quant_investment' GROUP BY state;"
```
Expected: `idle in transaction` = 0。连续采样 3 次（间隔 30s），交易时段外 WatchEngine 不 tick 属正常。

- [ ] **Step 5: 观察日志 5 分钟**

```bash
tail -100 ~/v2-api.log | grep -i "error\|exception\|QueuePool" | head
```
Expected: 无新增错误。

- [ ] **Step 6: 输出完成报告**（各 WP commit hash / 测试对比 / 生产验证结果），更新记忆 `fastapi-orm-session-pool-exhaustion` 的"残留"一节为"已清除"。

---

## 执行模型提示词（派发子 agent 时逐块粘贴，前面加通用规则块）

<details>
<summary>WP-0 提示词（Haiku）</summary>

```
你是 quantsys-v2 仓库的执行 agent。任务：只做基线快照，不改任何代码。
严格按 docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md 的 WP-0 五个 Step 执行。
所有命令真跑，输出原文记录。发现与计划"用法清单"不符的新用法时停手报告，禁止自行扩大范围。
最终输出：基线文件路径 + main hash + 测试 pass/fail 数字 + 清单对账结论。
```

</details>

<details>
<summary>WP-1 提示词（Sonnet）</summary>

```
你是 quantsys-v2 仓库的执行 agent。任务：实现 db_cursor + validators 基建。
计划文件：docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md，先读通用规则块，再严格执行 WP-1 的 Step 1-8。
代码已在计划中完整给出，逐字使用，禁止"改进"。TDD 顺序：先测试后实现。
worktree 名 wp1-db-cursor。完成后不 merge-back，先输出 diff 摘要等 Claude 终审。
```

</details>

<details>
<summary>WP-2 提示词（Sonnet，H 级加严）</summary>

```
你是 quantsys-v2 仓库的执行 agent。任务：StockPoolRepository 迁移（高风险，本仓库历史上在此翻车过一次：8f06ae1 契约破坏事件）。
计划文件：docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md，先读通用规则块与背景章节的"语义要点"，严格执行 WP-2 的 Step 1-10。
铁律：
- SQL 字符串、方法签名、_parse_row 逻辑、返回类型，逐字不动。你的唯一动作是替换游标获取与提交方式。
- 每个方法改完对照 diff 自查：删除的行只能涉及 self._get_cursor()/self.db.commit()/try-finally-close，新增的行只能是 with db_cursor(...) 与缩进。
- get_pool 是 get_by_id 的 alias，16 个生产调用方，禁删禁改签名。
worktree 名 wp2-stock-pool-repo。完成后输出：契约 diff 原文 + 残留检查输出 + 测试前后数字，等 Claude 终审，禁止自行 merge-back。
```

</details>

<details>
<summary>WP-3 提示词（Sonnet）</summary>

```
你是 quantsys-v2 仓库的执行 agent。任务：StrategyPerformanceRepository 迁移。
计划文件：docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md，先读通用规则块，严格执行 WP-3 全部 Step（改写模板参照计划 WP-2 Step 5）。
签名以源文件 grep 快照为准，禁止凭记忆。SQL 逐字不动。
worktree 名 wp3-strategy-perf-repo。完成后输出契约 diff 与测试对比，等 Claude 抽查后 merge-back。
```

</details>

<details>
<summary>WP-4 提示词（Sonnet）</summary>

```
你是 quantsys-v2 仓库的执行 agent。任务：9 个文件的 BaseRepository 直插用法改写。
计划文件：docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md，先读通用规则块，严格执行 WP-4 的 Step 1-10。
每处改写前先读原函数完整实现再动手；SQL 与业务逻辑逐字不动；只换连接获取/提交方式。
worktree 名 wp4-direct-usages。完成后输出残留检查输出与测试对比，然后按通用规则 10 merge-back。
```

</details>

<details>
<summary>WP-5 提示词（Sonnet）</summary>

```
你是 quantsys-v2 仓库的执行 agent。任务：删除 legacy base_repository.py 并全量回归。
前置确认：git log main --oneline -10 中必须能看到 WP-2/3/4 的提交，缺任何一个即停手报告。
计划文件：docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md，严格执行 WP-5 的 Step 1-8。
重点：_resolve_db_dsn 的 pytest 生产库安全检查逐字搬到 engine.py；orm/base_repository.py 与 async_base_repository.py 禁止误删。
worktree 名 wp5-delete-legacy。5099 冷启动冒烟必须真跑。完成后等 Claude 终审再 merge-back。
```

</details>

<details>
<summary>WP-6 提示词（Haiku/Sonnet）</summary>

```
你是运维执行 agent。任务：生产部署与验证。
计划文件：docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md，严格执行 WP-6 的 Step 1-6。
重启命令与日志路径以计划为准（launchd kickstart，~/v2-api.log）。
任何冒烟端点非 200 或出现 idle in transaction > 0：停手，贴出原始输出报告，禁止自行回滚或重试。
```

</details>

---

## Self-Review 结论（计划作者已执行）

- **Spec 覆盖**：用法清单 11 行全部映射到 WP（两个子类→WP-2/3，9 处直插→WP-4，_resolve_db_dsn×2→WP-5，test_base_repository→WP-5）。Flask 回滚栈唯一直插点（api/routes/signals.py:703）已含在 WP-4，Flask 栈整体删除不在本计划范围。
- **Placeholder 扫描**：WP-3 签名未列出是刻意为之——executor 必须从源文件 grep 快照（防幻觉，W1.1 教训），其余代码步骤均含完整代码。
- **类型一致性**：`db_cursor(commit=...)` / `validate_symbol` 命名在 WP-1 定义、WP-2/3/4/5 使用，全文一致。
- **并行安全**：WP-2/3/4 文件集交集为空（已验证清单）。
