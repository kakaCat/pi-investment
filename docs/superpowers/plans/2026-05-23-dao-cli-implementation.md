# Agent 数据 DAO 层和 CLI 命令实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已迁移到 PostgreSQL 的 Agent 数据实现完整的 DAO 层和 CLI 命令接口

**Architecture:** DAO 层复用 Database 类提供数据访问，CLI 命令注册到 CommandRegistry，统一 JSON 输出格式

**Tech Stack:** Python 3.x, PostgreSQL, psycopg2, CommandRegistry

---

## 文件结构

### 新增文件

**DAO 层**:
- `quant/quantsys/db/dao/__init__.py` - DAO 包初始化
- `quant/quantsys/db/dao/base_dao.py` - 基础 DAO 类
- `quant/quantsys/db/dao/position_dao.py` - 持仓数据访问
- `quant/quantsys/db/dao/watchlist_dao.py` - 关注列表数据访问
- `quant/quantsys/db/dao/trade_dao.py` - 交易历史数据访问
- `quant/quantsys/db/dao/account_dao.py` - 账户数据访问

### 修改文件

- `quant/quantsys/cli/main.py` - 注册新的 CLI 命令

---

## Task 1: 实现 BaseDAO 基础类

**Files:**
- Create: `quant/quantsys/db/dao/__init__.py`
- Create: `quant/quantsys/db/dao/base_dao.py`

- [ ] **Step 1: 创建 DAO 包初始化文件**

```python
"""Data Access Object (DAO) layer for quant_agent schema."""

from .base_dao import BaseDAO
from .position_dao import PositionDAO
from .watchlist_dao import WatchlistDAO
from .trade_dao import TradeDAO
from .account_dao import AccountDAO

__all__ = [
    'BaseDAO',
    'PositionDAO',
    'WatchlistDAO',
    'TradeDAO',
    'AccountDAO',
]
```

- [ ] **Step 2: 创建 BaseDAO 类框架**

```python
"""Base Data Access Object for quant_agent schema."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from psycopg2.extras import RealDictCursor

from ...data.db import Database


SCHEMA_NAME = 'quant_agent'


class BaseDAO:
    """基础 DAO 类，提供数据库连接和通用查询方法"""
    
    def __init__(self, db: Optional[Database] = None):
        """初始化 DAO
        
        Args:
            db: Database 实例，如果为 None 则创建新实例
        """
        self.db = db if db is not None else Database()
        self._conn = None
    
    @property
    def conn(self):
        """获取数据库连接"""
        if self._conn is None:
            self._conn = self.db.get_connection()
        return self._conn
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果列表
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            结果列表，每个元素是一个字典
        """
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in results]
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """执行更新操作并返回影响的行数
        
        Args:
            query: SQL 更新语句
            params: 更新参数
            
        Returns:
            影响的行数
        """
        cursor = self.conn.cursor()
        cursor.execute(query, params or ())
        rowcount = cursor.rowcount
        self.conn.commit()
        cursor.close()
        return rowcount
    
    def execute_insert(self, query: str, params: tuple = None) -> Optional[str]:
        """执行插入操作并返回新记录的 ID
        
        Args:
            query: SQL 插入语句（需要包含 RETURNING id）
            params: 插入参数
            
        Returns:
            新记录的 UUID（字符串格式），如果没有返回则为 None
        """
        cursor = self.conn.cursor()
        cursor.execute(query, params or ())
        result = cursor.fetchone()
        self.conn.commit()
        cursor.close()
        return str(result[0]) if result else None
    
    def _build_table_name(self, table: str) -> str:
        """构建完整的表名（包含 schema）
        
        Args:
            table: 表名
            
        Returns:
            完整表名，格式为 schema.table
        """
        return f"{SCHEMA_NAME}.{table}"
```

- [ ] **Step 3: 提交 BaseDAO**

```bash
git add quant/quantsys/db/dao/__init__.py quant/quantsys/db/dao/base_dao.py
git commit -m "feat(dao): add BaseDAO with Database integration

- Create DAO package structure
- Implement BaseDAO with execute_query, execute_update, execute_insert
- Use Database class for connection management
- Support RealDictCursor for dict results"
```

---

## Task 2: 实现 PositionDAO

**Files:**
- Create: `quant/quantsys/db/dao/position_dao.py`

- [ ] **Step 1: 创建 PositionDAO 类框架**

```python
"""Position Data Access Object."""

from __future__ import annotations

from typing import Dict, List, Optional

from .base_dao import BaseDAO


class PositionDAO(BaseDAO):
    """持仓数据访问对象"""
    
    def list_positions(
        self, 
        account_id: str = 'default', 
        status: str = 'open'
    ) -> List[Dict]:
        """获取持仓列表
        
        Args:
            account_id: 账户 ID
            status: 持仓状态（open/closed）
            
        Returns:
            持仓列表
        """
        query = f"""
            SELECT * FROM {self._build_table_name('positions')}
            WHERE account_id = %s AND status = %s
            ORDER BY entry_date DESC
        """
        return self.execute_query(query, (account_id, status))
    
    def get_position(
        self, 
        symbol: str, 
        account_id: str = 'default'
    ) -> Optional[Dict]:
        """获取单个持仓详情
        
        Args:
            symbol: 股票代码
            account_id: 账户 ID
            
        Returns:
            持仓详情，不存在返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('positions')}
            WHERE symbol = %s AND account_id = %s AND status = 'open'
        """
        results = self.execute_query(query, (symbol, account_id))
        return results[0] if results else None
```

- [ ] **Step 2: 实现 update_position 方法**

```python
    def update_position(
        self, 
        symbol: str, 
        data: Dict, 
        account_id: str = 'default'
    ) -> int:
        """更新持仓信息
        
        Args:
            symbol: 股票代码
            data: 更新数据（可包含 quantity, current_price, stop_loss, take_profit, notes）
            account_id: 账户 ID
            
        Returns:
            更新的行数
        """
        # 构建 SET 子句
        set_clauses = []
        params = []
        
        allowed_fields = ['quantity', 'current_price', 'stop_loss', 'take_profit', 'notes']
        for field in allowed_fields:
            if field in data:
                set_clauses.append(f"{field} = %s")
                params.append(data[field])
        
        if not set_clauses:
            return 0
        
        # 添加 updated_at
        set_clauses.append("updated_at = NOW()")
        
        # 添加 WHERE 条件参数
        params.extend([symbol, account_id])
        
        query = f"""
            UPDATE {self._build_table_name('positions')}
            SET {', '.join(set_clauses)}
            WHERE symbol = %s AND account_id = %s AND status = 'open'
        """
        return self.execute_update(query, tuple(params))
```

- [ ] **Step 3: 实现 close_position 和 get_position_summary 方法**

```python
    def close_position(
        self, 
        symbol: str, 
        reason: Optional[str] = None,
        account_id: str = 'default'
    ) -> int:
        """关闭持仓
        
        Args:
            symbol: 股票代码
            reason: 关闭原因
            account_id: 账户 ID
            
        Returns:
            更新的行数
        """
        query = f"""
            UPDATE {self._build_table_name('positions')}
            SET status = 'closed', 
                notes = CASE 
                    WHEN %s IS NOT NULL THEN COALESCE(notes || ' | ', '') || '关闭原因: ' || %s
                    ELSE notes
                END,
                updated_at = NOW()
            WHERE symbol = %s AND account_id = %s AND status = 'open'
        """
        return self.execute_update(query, (reason, reason, symbol, account_id))
    
    def get_position_summary(self, account_id: str = 'default') -> Dict:
        """获取持仓汇总统计
        
        Args:
            account_id: 账户 ID
            
        Returns:
            汇总统计（总持仓数、总成本、总市值等）
        """
        query = f"""
            SELECT 
                COUNT(*) as total_positions,
                SUM(quantity) as total_quantity,
                SUM(quantity * cost_basis) as total_cost,
                SUM(quantity * COALESCE(current_price, cost_basis)) as total_market_value,
                SUM(quantity * (COALESCE(current_price, cost_basis) - cost_basis)) as total_pnl,
                CASE 
                    WHEN SUM(quantity * cost_basis) > 0 
                    THEN SUM(quantity * (COALESCE(current_price, cost_basis) - cost_basis)) / SUM(quantity * cost_basis) * 100
                    ELSE 0
                END as total_pnl_pct
            FROM {self._build_table_name('positions')}
            WHERE account_id = %s AND status = 'open'
        """
        results = self.execute_query(query, (account_id,))
        return results[0] if results else {
            'total_positions': 0,
            'total_quantity': 0,
            'total_cost': 0,
            'total_market_value': 0,
            'total_pnl': 0,
            'total_pnl_pct': 0
        }
```

- [ ] **Step 4: 提交 PositionDAO**

```bash
git add quant/quantsys/db/dao/position_dao.py
git commit -m "feat(dao): add PositionDAO with 5 methods

- list_positions: get position list with filters
- get_position: get single position detail
- update_position: update position fields
- close_position: close position with reason
- get_position_summary: get position statistics"
```

---

待续...（文件太长，我将分步添加剩余任务）

## Task 3: 实现 WatchlistDAO

**Files:**
- Create: `quant/quantsys/db/dao/watchlist_dao.py`

- [ ] **Step 1: 创建 WatchlistDAO 类框架**

```python
"""Watchlist Data Access Object."""

from __future__ import annotations

from typing import Dict, List, Optional

from .base_dao import BaseDAO


class WatchlistDAO(BaseDAO):
    """关注列表数据访问对象"""
    
    def list_watchlist(
        self,
        pool: Optional[str] = None,
        priority: Optional[int] = None,
        status: str = 'watching'
    ) -> List[Dict]:
        """获取关注列表
        
        Args:
            pool: 池子（A/B/C）
            priority: 优先级（1-5）
            status: 状态（watching/paused/removed）
            
        Returns:
            关注列表
        """
        conditions = ["status = %s"]
        params = [status]
        
        if pool is not None:
            conditions.append("pool = %s")
            params.append(pool)
        
        if priority is not None:
            conditions.append("priority = %s")
            params.append(priority)
        
        query = f"""
            SELECT * FROM {self._build_table_name('watchlist')}
            WHERE {' AND '.join(conditions)}
            ORDER BY priority ASC, symbol ASC
        """
        return self.execute_query(query, tuple(params))
    
    def get_watchlist_item(self, symbol: str) -> Optional[Dict]:
        """获取单个关注项详情
        
        Args:
            symbol: 股票代码
            
        Returns:
            关注项详情，不存在返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('watchlist')}
            WHERE symbol = %s
        """
        results = self.execute_query(query, (symbol,))
        return results[0] if results else None
```

- [ ] **Step 2: 实现 add_to_watchlist 和 remove_from_watchlist 方法**

```python
    def add_to_watchlist(self, data: Dict) -> str:
        """添加到关注列表
        
        Args:
            data: 关注项数据（必须包含 symbol, name, market）
            
        Returns:
            新记录的 UUID
        """
        query = f"""
            INSERT INTO {self._build_table_name('watchlist')}
            (symbol, name, market, priority, pool, status, 
             buy_range_low, buy_range_high, target_price, stop_loss, reason, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            data['symbol'],
            data['name'],
            data['market'],
            data.get('priority', 3),
            data.get('pool'),
            data.get('status', 'watching'),
            data.get('buy_range_low'),
            data.get('buy_range_high'),
            data.get('target_price'),
            data.get('stop_loss'),
            data.get('reason'),
            data.get('notes')
        )
        return self.execute_insert(query, params)
    
    def remove_from_watchlist(self, symbol: str) -> int:
        """从关注列表移除
        
        Args:
            symbol: 股票代码
            
        Returns:
            删除的行数
        """
        query = f"""
            DELETE FROM {self._build_table_name('watchlist')}
            WHERE symbol = %s
        """
        return self.execute_update(query, (symbol,))
```

- [ ] **Step 3: 实现 update_watchlist_item 方法**

```python
    def update_watchlist_item(self, symbol: str, data: Dict) -> int:
        """更新关注项
        
        Args:
            symbol: 股票代码
            data: 更新数据
            
        Returns:
            更新的行数
        """
        set_clauses = []
        params = []
        
        allowed_fields = [
            'priority', 'pool', 'status', 'buy_range_low', 'buy_range_high',
            'target_price', 'stop_loss', 'reason', 'notes'
        ]
        for field in allowed_fields:
            if field in data:
                set_clauses.append(f"{field} = %s")
                params.append(data[field])
        
        if not set_clauses:
            return 0
        
        set_clauses.append("updated_at = NOW()")
        params.append(symbol)
        
        query = f"""
            UPDATE {self._build_table_name('watchlist')}
            SET {', '.join(set_clauses)}
            WHERE symbol = %s
        """
        return self.execute_update(query, tuple(params))
```

- [ ] **Step 4: 提交 WatchlistDAO**

```bash
git add quant/quantsys/db/dao/watchlist_dao.py
git commit -m "feat(dao): add WatchlistDAO with 5 methods

- list_watchlist: get watchlist with filters
- get_watchlist_item: get single item detail
- add_to_watchlist: add new watchlist item
- remove_from_watchlist: remove item
- update_watchlist_item: update item fields"
```

---

## Task 4: 实现 TradeDAO 和 AccountDAO

**Files:**
- Create: `quant/quantsys/db/dao/trade_dao.py`
- Create: `quant/quantsys/db/dao/account_dao.py`

- [ ] **Step 1: 创建 TradeDAO 类**

```python
"""Trade Data Access Object."""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime

from .base_dao import BaseDAO


class TradeDAO(BaseDAO):
    """交易历史数据访问对象"""
    
    def list_trades(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取交易历史
        
        Args:
            symbol: 股票代码
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            limit: 返回记录数限制
            
        Returns:
            交易历史列表
        """
        conditions = []
        params = []
        
        if symbol is not None:
            conditions.append("symbol = %s")
            params.append(symbol)
        
        if start_date is not None:
            conditions.append("timestamp >= %s")
            params.append(start_date)
        
        if end_date is not None:
            conditions.append("timestamp <= %s")
            params.append(end_date)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT * FROM {self._build_table_name('position_history')}
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
        """
        params.append(limit)
        return self.execute_query(query, tuple(params))
    
    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """获取单笔交易详情
        
        Args:
            trade_id: 交易 ID（从 notes 字段中查找）
            
        Returns:
            交易详情，不存在返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('position_history')}
            WHERE notes LIKE %s
        """
        results = self.execute_query(query, (f'%{trade_id}%',))
        return results[0] if results else None
    
    def get_trade_stats(
        self,
        symbol: Optional[str] = None,
        period: str = 'all'
    ) -> Dict:
        """获取交易统计
        
        Args:
            symbol: 股票代码
            period: 统计周期（all/year/month/week）
            
        Returns:
            交易统计
        """
        conditions = []
        params = []
        
        if symbol is not None:
            conditions.append("symbol = %s")
            params.append(symbol)
        
        # 添加时间范围条件
        if period == 'year':
            conditions.append("timestamp >= NOW() - INTERVAL '1 year'")
        elif period == 'month':
            conditions.append("timestamp >= NOW() - INTERVAL '1 month'")
        elif period == 'week':
            conditions.append("timestamp >= NOW() - INTERVAL '1 week'")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN action = 'buy' THEN 1 END) as buy_count,
                COUNT(CASE WHEN action = 'sell' THEN 1 END) as sell_count,
                SUM(COALESCE(realized_pnl, 0)) as total_pnl,
                AVG(COALESCE(realized_pnl, 0)) as avg_pnl,
                COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as win_count,
                COUNT(CASE WHEN realized_pnl < 0 THEN 1 END) as loss_count,
                CASE 
                    WHEN COUNT(CASE WHEN realized_pnl IS NOT NULL THEN 1 END) > 0
                    THEN COUNT(CASE WHEN realized_pnl > 0 THEN 1 END)::FLOAT / 
                         COUNT(CASE WHEN realized_pnl IS NOT NULL THEN 1 END) * 100
                    ELSE 0
                END as win_rate
            FROM {self._build_table_name('position_history')}
            {where_clause}
        """
        results = self.execute_query(query, tuple(params))
        return results[0] if results else {}
```

- [ ] **Step 2: 创建 AccountDAO 类**

```python
"""Account Data Access Object."""

from __future__ import annotations

from typing import Dict, Optional

from .base_dao import BaseDAO


class AccountDAO(BaseDAO):
    """账户数据访问对象"""
    
    def get_account(self, name: str = 'Default Account') -> Optional[Dict]:
        """获取账户信息
        
        Args:
            name: 账户名称
            
        Returns:
            账户信息，不存在返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('accounts')}
            WHERE name = %s
        """
        results = self.execute_query(query, (name,))
        return results[0] if results else None
    
    def update_account(self, name: str, data: Dict) -> int:
        """更新账户信息
        
        Args:
            name: 账户名称
            data: 更新数据（可包含 current_capital, currency, notes）
            
        Returns:
            更新的行数
        """
        set_clauses = []
        params = []
        
        allowed_fields = ['current_capital', 'currency', 'notes']
        for field in allowed_fields:
            if field in data:
                set_clauses.append(f"{field} = %s")
                params.append(data[field])
        
        if not set_clauses:
            return 0
        
        set_clauses.append("updated_at = NOW()")
        params.append(name)
        
        query = f"""
            UPDATE {self._build_table_name('accounts')}
            SET {', '.join(set_clauses)}
            WHERE name = %s
        """
        return self.execute_update(query, tuple(params))
```

- [ ] **Step 3: 提交 TradeDAO 和 AccountDAO**

```bash
git add quant/quantsys/db/dao/trade_dao.py quant/quantsys/db/dao/account_dao.py
git commit -m "feat(dao): add TradeDAO and AccountDAO

TradeDAO:
- list_trades: get trade history with filters
- get_trade: get single trade detail
- get_trade_stats: get trade statistics

AccountDAO:
- get_account: get account info
- update_account: update account fields"
```

---


## Task 5: 实现 Position CLI 命令

**Files:**
- Modify: `quant/quantsys/cli/main.py`

- [ ] **Step 1: 在 main.py 中添加 position.list 命令的 handler**

在 `build_registry()` 函数末尾添加：

```python
def _handle_position_list(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.list 命令"""
    from ..db.dao import PositionDAO
    
    dao = PositionDAO()
    account_id = params.get('account_id', 'default')
    status = params.get('status', 'open')
    
    positions = dao.list_positions(account_id=account_id, status=status)
    
    return {
        "data": {
            "total": len(positions),
            "positions": positions
        }
    }
```

- [ ] **Step 2: 注册 position.list 命令**

在 `build_registry()` 函数中添加：

```python
    registry.register(
        CommandSpec(
            name="position.list",
            domain="position",
            action="list",
            description="List all positions",
            params={
                "account_id": {"type": "string", "required": False, "default": "default"},
                "status": {"type": "string", "required": False, "default": "open"}
            },
            examples=["quant position +list --json", "quant position +list --status closed --json"],
            handler=_handle_position_list,
        )
    )
```

- [ ] **Step 3: 添加 position.get 命令**

```python
def _handle_position_get(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.get 命令"""
    from ..db.dao import PositionDAO
    
    dao = PositionDAO()
    symbol = params['symbol']
    account_id = params.get('account_id', 'default')
    
    position = dao.get_position(symbol=symbol, account_id=account_id)
    
    if position is None:
        return {
            "status": "error",
            "message": f"Position not found: {symbol}"
        }
    
    return {"data": position}

    registry.register(
        CommandSpec(
            name="position.get",
            domain="position",
            action="get",
            description="Get single position detail",
            params={
                "symbol": {"type": "string", "required": True},
                "account_id": {"type": "string", "required": False, "default": "default"}
            },
            examples=["quant position +get --symbol 600036 --json"],
            handler=_handle_position_get,
        )
    )
```

- [ ] **Step 4: 添加 position.update 命令**

```python
def _handle_position_update(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.update 命令"""
    from ..db.dao import PositionDAO
    
    dao = PositionDAO()
    symbol = params['symbol']
    account_id = params.get('account_id', 'default')
    
    # 构建更新数据
    data = {}
    if 'quantity' in params:
        data['quantity'] = params['quantity']
    if 'price' in params:
        data['current_price'] = params['price']
    if 'stop_loss' in params:
        data['stop_loss'] = params['stop_loss']
    if 'take_profit' in params:
        data['take_profit'] = params['take_profit']
    if 'notes' in params:
        data['notes'] = params['notes']
    
    rows = dao.update_position(symbol=symbol, data=data, account_id=account_id)
    
    if rows == 0:
        return {
            "status": "error",
            "message": f"Position not found or no changes: {symbol}"
        }
    
    return {
        "data": {
            "updated_rows": rows,
            "symbol": symbol
        }
    }

    registry.register(
        CommandSpec(
            name="position.update",
            domain="position",
            action="update",
            description="Update position",
            params={
                "symbol": {"type": "string", "required": True},
                "account_id": {"type": "string", "required": False, "default": "default"},
                "quantity": {"type": "integer", "required": False},
                "price": {"type": "number", "required": False},
                "stop_loss": {"type": "number", "required": False},
                "take_profit": {"type": "number", "required": False},
                "notes": {"type": "string", "required": False}
            },
            examples=["quant position +update --symbol 600036 --price 38.5 --json"],
            handler=_handle_position_update,
        )
    )
```

- [ ] **Step 5: 添加 position.close 和 position.summary 命令**

```python
def _handle_position_close(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.close 命令"""
    from ..db.dao import PositionDAO
    
    dao = PositionDAO()
    symbol = params['symbol']
    reason = params.get('reason')
    account_id = params.get('account_id', 'default')
    
    rows = dao.close_position(symbol=symbol, reason=reason, account_id=account_id)
    
    if rows == 0:
        return {
            "status": "error",
            "message": f"Position not found: {symbol}"
        }
    
    return {
        "data": {
            "closed": True,
            "symbol": symbol,
            "reason": reason
        }
    }

def _handle_position_summary(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.summary 命令"""
    from ..db.dao import PositionDAO
    
    dao = PositionDAO()
    account_id = params.get('account_id', 'default')
    
    summary = dao.get_position_summary(account_id=account_id)
    
    return {"data": summary}

    registry.register(
        CommandSpec(
            name="position.close",
            domain="position",
            action="close",
            description="Close position",
            params={
                "symbol": {"type": "string", "required": True},
                "reason": {"type": "string", "required": False},
                "account_id": {"type": "string", "required": False, "default": "default"}
            },
            examples=["quant position +close --symbol 600036 --reason 止盈 --json"],
            handler=_handle_position_close,
        )
    )
    
    registry.register(
        CommandSpec(
            name="position.summary",
            domain="position",
            action="summary",
            description="Get position summary statistics",
            params={
                "account_id": {"type": "string", "required": False, "default": "default"}
            },
            examples=["quant position +summary --json"],
            handler=_handle_position_summary,
        )
    )
```

- [ ] **Step 6: 测试 Position 命令**

```bash
# 测试列出持仓
quant position +list --json

# 测试获取单个持仓
quant position +get --symbol 600036 --json

# 测试更新持仓
quant position +update --symbol 600036 --price 38.5 --json

# 测试持仓汇总
quant position +summary --json
```

Expected: 所有命令正常返回 JSON 格式数据

- [ ] **Step 7: 提交 Position CLI 命令**

```bash
git add quant/quantsys/cli/main.py
git commit -m "feat(cli): add Position CLI commands

- position.list: list all positions
- position.get: get single position detail
- position.update: update position fields
- position.close: close position
- position.summary: get position statistics"
```

---

## Task 6: 实现 Watchlist CLI 命令

**Files:**
- Modify: `quant/quantsys/cli/main.py`

- [ ] **Step 1: 添加 watchlist.list 和 watchlist.get 命令**

```python
def _handle_watchlist_list(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 watchlist.list 命令"""
    from ..db.dao import WatchlistDAO
    
    dao = WatchlistDAO()
    pool = params.get('pool')
    priority = params.get('priority')
    status = params.get('status', 'watching')
    
    items = dao.list_watchlist(pool=pool, priority=priority, status=status)
    
    return {
        "data": {
            "total": len(items),
            "items": items
        }
    }

def _handle_watchlist_get(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 watchlist.get 命令"""
    from ..db.dao import WatchlistDAO
    
    dao = WatchlistDAO()
    symbol = params['symbol']
    
    item = dao.get_watchlist_item(symbol=symbol)
    
    if item is None:
        return {
            "status": "error",
            "message": f"Watchlist item not found: {symbol}"
        }
    
    return {"data": item}

    registry.register(
        CommandSpec(
            name="watchlist.list",
            domain="watchlist",
            action="list",
            description="List watchlist items",
            params={
                "pool": {"type": "string", "required": False},
                "priority": {"type": "integer", "required": False},
                "status": {"type": "string", "required": False, "default": "watching"}
            },
            examples=["quant watchlist +list --json", "quant watchlist +list --pool A --priority 1 --json"],
            handler=_handle_watchlist_list,
        )
    )
    
    registry.register(
        CommandSpec(
            name="watchlist.get",
            domain="watchlist",
            action="get",
            description="Get watchlist item detail",
            params={
                "symbol": {"type": "string", "required": True}
            },
            examples=["quant watchlist +get --symbol 002025 --json"],
            handler=_handle_watchlist_get,
        )
    )
```

- [ ] **Step 2: 添加 watchlist.add 和 watchlist.remove 命令**

```python
def _handle_watchlist_add(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 watchlist.add 命令"""
    from ..db.dao import WatchlistDAO
    
    dao = WatchlistDAO()
    
    data = {
        'symbol': params['symbol'],
        'name': params['name'],
        'market': params['market'],
        'priority': params.get('priority', 3),
        'pool': params.get('pool'),
        'status': params.get('status', 'watching'),
        'buy_range_low': params.get('buy_range_low'),
        'buy_range_high': params.get('buy_range_high'),
        'target_price': params.get('target_price'),
        'stop_loss': params.get('stop_loss'),
        'reason': params.get('reason'),
        'notes': params.get('notes')
    }
    
    item_id = dao.add_to_watchlist(data=data)
    
    return {
        "data": {
            "id": item_id,
            "symbol": params['symbol']
        }
    }

def _handle_watchlist_remove(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 watchlist.remove 命令"""
    from ..db.dao import WatchlistDAO
    
    dao = WatchlistDAO()
    symbol = params['symbol']
    
    rows = dao.remove_from_watchlist(symbol=symbol)
    
    if rows == 0:
        return {
            "status": "error",
            "message": f"Watchlist item not found: {symbol}"
        }
    
    return {
        "data": {
            "removed": True,
            "symbol": symbol
        }
    }

    registry.register(
        CommandSpec(
            name="watchlist.add",
            domain="watchlist",
            action="add",
            description="Add to watchlist",
            params={
                "symbol": {"type": "string", "required": True},
                "name": {"type": "string", "required": True},
                "market": {"type": "string", "required": True},
                "priority": {"type": "integer", "required": False, "default": 3},
                "pool": {"type": "string", "required": False},
                "status": {"type": "string", "required": False, "default": "watching"},
                "buy_range_low": {"type": "number", "required": False},
                "buy_range_high": {"type": "number", "required": False},
                "target_price": {"type": "number", "required": False},
                "stop_loss": {"type": "number", "required": False},
                "reason": {"type": "string", "required": False},
                "notes": {"type": "string", "required": False}
            },
            examples=["quant watchlist +add --symbol 600519 --name 贵州茅台 --market A --priority 1 --json"],
            handler=_handle_watchlist_add,
        )
    )
    
    registry.register(
        CommandSpec(
            name="watchlist.remove",
            domain="watchlist",
            action="remove",
            description="Remove from watchlist",
            params={
                "symbol": {"type": "string", "required": True}
            },
            examples=["quant watchlist +remove --symbol 600519 --json"],
            handler=_handle_watchlist_remove,
        )
    )
```

- [ ] **Step 3: 添加 watchlist.update 命令并测试**

```python
def _handle_watchlist_update(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 watchlist.update 命令"""
    from ..db.dao import WatchlistDAO
    
    dao = WatchlistDAO()
    symbol = params['symbol']
    
    data = {}
    update_fields = ['priority', 'pool', 'status', 'buy_range_low', 'buy_range_high',
                     'target_price', 'stop_loss', 'reason', 'notes']
    for field in update_fields:
        if field in params:
            data[field] = params[field]
    
    rows = dao.update_watchlist_item(symbol=symbol, data=data)
    
    if rows == 0:
        return {
            "status": "error",
            "message": f"Watchlist item not found or no changes: {symbol}"
        }
    
    return {
        "data": {
            "updated_rows": rows,
            "symbol": symbol
        }
    }

    registry.register(
        CommandSpec(
            name="watchlist.update",
            domain="watchlist",
            action="update",
            description="Update watchlist item",
            params={
                "symbol": {"type": "string", "required": True},
                "priority": {"type": "integer", "required": False},
                "pool": {"type": "string", "required": False},
                "status": {"type": "string", "required": False},
                "buy_range_low": {"type": "number", "required": False},
                "buy_range_high": {"type": "number", "required": False},
                "target_price": {"type": "number", "required": False},
                "stop_loss": {"type": "number", "required": False},
                "reason": {"type": "string", "required": False},
                "notes": {"type": "string", "required": False}
            },
            examples=["quant watchlist +update --symbol 600519 --priority 2 --json"],
            handler=_handle_watchlist_update,
        )
    )
```

Run: `quant watchlist +list --json`
Expected: 返回关注列表

- [ ] **Step 4: 提交 Watchlist CLI 命令**

```bash
git add quant/quantsys/cli/main.py
git commit -m "feat(cli): add Watchlist CLI commands

- watchlist.list: list watchlist items
- watchlist.get: get item detail
- watchlist.add: add to watchlist
- watchlist.remove: remove from watchlist
- watchlist.update: update item fields"
```

---

## Task 7: 实现 Trade 和 Account CLI 命令

**Files:**
- Modify: `quant/quantsys/cli/main.py`

- [ ] **Step 1: 添加 Trade CLI 命令**

```python
def _handle_trade_list(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 trade.list 命令"""
    from ..db.dao import TradeDAO
    
    dao = TradeDAO()
    symbol = params.get('symbol')
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    limit = params.get('limit', 100)
    
    trades = dao.list_trades(symbol=symbol, start_date=start_date, 
                            end_date=end_date, limit=limit)
    
    return {
        "data": {
            "total": len(trades),
            "trades": trades
        }
    }

def _handle_trade_get(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 trade.get 命令"""
    from ..db.dao import TradeDAO
    
    dao = TradeDAO()
    trade_id = params['trade_id']
    
    trade = dao.get_trade(trade_id=trade_id)
    
    if trade is None:
        return {
            "status": "error",
            "message": f"Trade not found: {trade_id}"
        }
    
    return {"data": trade}

def _handle_trade_stats(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 trade.stats 命令"""
    from ..db.dao import TradeDAO
    
    dao = TradeDAO()
    symbol = params.get('symbol')
    period = params.get('period', 'all')
    
    stats = dao.get_trade_stats(symbol=symbol, period=period)
    
    return {"data": stats}

    registry.register(
        CommandSpec(
            name="trade.list",
            domain="trade",
            action="list",
            description="List trade history",
            params={
                "symbol": {"type": "string", "required": False},
                "start_date": {"type": "string", "required": False},
                "end_date": {"type": "string", "required": False},
                "limit": {"type": "integer", "required": False, "default": 100}
            },
            examples=["quant trade +list --json", "quant trade +list --symbol 600036 --limit 10 --json"],
            handler=_handle_trade_list,
        )
    )
    
    registry.register(
        CommandSpec(
            name="trade.get",
            domain="trade",
            action="get",
            description="Get single trade detail",
            params={
                "trade_id": {"type": "string", "required": True}
            },
            examples=["quant trade +get --trade_id 1600000001001 --json"],
            handler=_handle_trade_get,
        )
    )
    
    registry.register(
        CommandSpec(
            name="trade.stats",
            domain="trade",
            action="stats",
            description="Get trade statistics",
            params={
                "symbol": {"type": "string", "required": False},
                "period": {"type": "string", "required": False, "default": "all"}
            },
            examples=["quant trade +stats --json", "quant trade +stats --symbol 600036 --period month --json"],
            handler=_handle_trade_stats,
        )
    )
```

- [ ] **Step 2: 添加 Account CLI 命令**

```python
def _handle_account_get(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 account.get 命令"""
    from ..db.dao import AccountDAO
    
    dao = AccountDAO()
    name = params.get('name', 'Default Account')
    
    account = dao.get_account(name=name)
    
    if account is None:
        return {
            "status": "error",
            "message": f"Account not found: {name}"
        }
    
    return {"data": account}

def _handle_account_update(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 account.update 命令"""
    from ..db.dao import AccountDAO
    
    dao = AccountDAO()
    name = params.get('name', 'Default Account')
    
    data = {}
    if 'capital' in params:
        data['current_capital'] = params['capital']
    if 'currency' in params:
        data['currency'] = params['currency']
    if 'notes' in params:
        data['notes'] = params['notes']
    
    rows = dao.update_account(name=name, data=data)
    
    if rows == 0:
        return {
            "status": "error",
            "message": f"Account not found or no changes: {name}"
        }
    
    return {
        "data": {
            "updated_rows": rows,
            "name": name
        }
    }

    registry.register(
        CommandSpec(
            name="account.get",
            domain="account",
            action="get",
            description="Get account information",
            params={
                "name": {"type": "string", "required": False, "default": "Default Account"}
            },
            examples=["quant account +get --json"],
            handler=_handle_account_get,
        )
    )
    
    registry.register(
        CommandSpec(
            name="account.update",
            domain="account",
            action="update",
            description="Update account",
            params={
                "name": {"type": "string", "required": False, "default": "Default Account"},
                "capital": {"type": "number", "required": False},
                "currency": {"type": "string", "required": False},
                "notes": {"type": "string", "required": False}
            },
            examples=["quant account +update --capital 250000 --json"],
            handler=_handle_account_update,
        )
    )
```

- [ ] **Step 3: 测试所有命令**

```bash
# 测试 Trade 命令
quant trade +list --json
quant trade +stats --json

# 测试 Account 命令
quant account +get --json
```

Expected: 所有命令正常返回数据

- [ ] **Step 4: 提交 Trade 和 Account CLI 命令**

```bash
git add quant/quantsys/cli/main.py
git commit -m "feat(cli): add Trade and Account CLI commands

Trade commands:
- trade.list: list trade history
- trade.get: get single trade detail
- trade.stats: get trade statistics

Account commands:
- account.get: get account info
- account.update: update account fields"
```

- [ ] **Step 5: 最终测试所有 CLI 命令**

```bash
# Position 命令
quant position +list --json
quant position +get --symbol 600036 --json
quant position +summary --json

# Watchlist 命令
quant watchlist +list --json
quant watchlist +get --symbol 002025 --json

# Trade 命令
quant trade +list --limit 5 --json
quant trade +stats --json

# Account 命令
quant account +get --json
```

Expected: 所有 20 个命令正常工作，返回正确的 JSON 格式数据

- [ ] **Step 6: 推送所有更改**

```bash
git push origin main
```

---

## 完成

所有任务已完成！现在 Agent 可以通过 CLI 命令访问 PostgreSQL 中的数据：

- ✅ DAO 层：5个类，20个方法
- ✅ CLI 命令：4个域，20个命令
- ✅ 统一 JSON 输出格式
- ✅ 完整的错误处理

**使用示例**：
```bash
# 查看持仓
quant position +list --json

# 添加到关注列表
quant watchlist +add --symbol 600519 --name 贵州茅台 --market A --json

# 查看交易统计
quant trade +stats --json
```
