"""
ORM模块 - SQLAlchemy ORM支持

提供：
1. Session管理（scoped_session，线程安全）
2. Base类（所有Model的基类）
3. BaseORMRepository（通用CRUD操作）
4. TimestampMixin（自动时间戳）

使用指南：
    # 1. 应用启动时初始化ORM
    from infrastructure.persistence.orm import init_orm
    init_orm()

    # 2. 定义Model
    from infrastructure.persistence.orm import Base
    class Stock(Base):
        __tablename__ = 'stocks'
        __table_args__ = {'schema': 'quant'}
        symbol = Column(String(10), primary_key=True)

    # 3. 创建Repository
    from infrastructure.persistence.orm import BaseORMRepository
    class StockORMRepository(BaseORMRepository[Stock]):
        model = Stock

    # 4. 使用Repository
    repo = StockORMRepository()
    stock = repo.get_by_id('000001')

    # 5. 请求/Job结束时清理
    from infrastructure.persistence.orm import close_session
    close_session()
"""

from .config import (
    Base,
    init_orm,
    get_session,
    close_session,
    close_orm,
    get_engine,
    is_initialized
)
from .base import TimestampMixin, to_dict
from .base_repository import BaseORMRepository

# 向后兼容别名
get_db_session = get_session

__all__ = [
    # 核心
    'Base',
    'init_orm',
    'get_session',
    'get_db_session',  # 向后兼容
    'close_session',
    'close_orm',
    'get_engine',
    'is_initialized',

    # Mixin和工具
    'TimestampMixin',
    'to_dict',

    # Repository基类
    'BaseORMRepository',
]
