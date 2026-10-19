"""持久层 ORM 基座（S11 · Slice B-1 迁入 qs_kernel）。

旧路径 ``infrastructure.persistence.orm`` 由 L1 侧同名 shim 包转发到本包：
已迁子模块（base / base_repository / async_base / async_config / config /
session_guard）通过 sys.modules 别名绑定到本包模块，models 业务表模型仍留在 L1。

使用指南：
    # 1. 应用启动时初始化ORM
    from qs_kernel.infrastructure.persistence.orm import init_orm
    init_orm()

    # 2. 定义Model
    from qs_kernel.infrastructure.persistence.orm import Base
    class Stock(Base):
        __tablename__ = 'stocks'
        __table_args__ = {'schema': 'quant'}
        symbol = Column(String(10), primary_key=True)

    # 3. 创建Repository
    from qs_kernel.infrastructure.persistence.orm import BaseORMRepository
    class StockORMRepository(BaseORMRepository[Stock]):
        model = Stock

    # 4. 使用Repository
    repo = StockORMRepository()
    stock = repo.get_by_id('000001')

    # 5. 请求/Job结束时清理
    from qs_kernel.infrastructure.persistence.orm import close_session
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