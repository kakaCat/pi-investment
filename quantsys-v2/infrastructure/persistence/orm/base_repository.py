"""
ORM基础Repository - 提供通用CRUD操作

所有ORM Repository应继承此类，获得：
1. 自动Session管理
2. 通用查询方法（get_by_id, list_all等）
3. 通用写入方法（create, update, delete）
4. 类型提示支持
"""
import logging
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .config import get_session
from .base import Base

logger = logging.getLogger(__name__)

# 泛型类型变量
T = TypeVar('T', bound=Base)


class BaseORMRepository(Generic[T]):
    """ORM基础Repository

    使用示例：
        class StockORMRepository(BaseORMRepository[Stock]):
            model = Stock

            def get_by_symbol(self, symbol: str) -> Optional[Stock]:
                return self.session.query(self.model).filter_by(symbol=symbol).first()

    特性：
        - 泛型支持：IDE可以自动推断返回类型
        - 自动Session管理：通过scoped_session
        - 事务支持：commit/rollback
        - 异常处理：统一捕获SQLAlchemy异常
    """

    # 子类必须设置此属性
    model: Type[T] = None

    def __init__(self):
        """初始化Repository

        自动获取当前线程的Session（通过scoped_session）
        """
        if self.model is None:
            raise ValueError(f"{self.__class__.__name__} must set 'model' attribute")

        self._session: Optional[Session] = None

    @property
    def session(self) -> Session:
        """获取Session（懒加载）"""
        if self._session is None:
            self._session = get_session()
        return self._session

    def _get_cursor(self):
        """向后兼容旧 BaseRepository 的裸 cursor 接口。

        遗留服务（data_gap_detector / data_validator / strategy_weight_adjuster
        / risk_check_service / signals 路由等）仍用原生 SQL + cursor 访问数据，
        但注入的 repo 已迁移为 ORM 版——缺少本方法时抛 AttributeError，
        曾被上层吞掉导致 data_quality_check "检查0只股票、评分100" 的假成功
        （2026-07-17 起，2026-07-23 定位）。

        Returns:
            psycopg2 RealDictCursor（行以 dict 返回）。调用方负责 close()。
            连接从 Engine 池 lazy 获取（pool_pre_ping 自动处理坏连接），
            挂在实例上复用，关闭后下次调用自动重建。
        """
        from psycopg2.extras import RealDictCursor
        from infrastructure.persistence.database.engine import get_engine

        if getattr(self, '_raw_conn', None) is None or self._raw_conn.closed:
            self._raw_conn = get_engine().connect()
        return self._raw_conn.connection.cursor(cursor_factory=RealDictCursor)

    def get_by_id(self, id_value: Any) -> Optional[T]:
        """根据主键获取对象

        Args:
            id_value: 主键值

        Returns:
            对象实例，不存在返回None
        """
        try:
            return self.session.query(self.model).get(id_value)
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by id={id_value}: {e}")
            return None

    def list_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """列出所有对象

        Args:
            limit: 返回数量限制
            offset: 跳过的数量

        Returns:
            对象列表
        """
        try:
            query = self.session.query(self.model)
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error listing {self.model.__name__}: {e}")
            return []

    def count(self) -> int:
        """统计总数"""
        try:
            return self.session.query(self.model).count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            return 0

    def create(self, obj: T, commit: bool = True) -> Optional[T]:
        """创建对象

        Args:
            obj: 要创建的对象
            commit: 是否立即提交（默认True）

        Returns:
            创建后的对象（包含自动生成的ID等），失败返回None
        """
        try:
            self.session.add(obj)
            if commit:
                self.session.commit()
                self.session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            if commit:
                self.session.rollback()
            return None

    def create_batch(self, objs: List[T], commit: bool = True) -> bool:
        """批量创建对象

        Args:
            objs: 对象列表
            commit: 是否立即提交

        Returns:
            成功返回True
        """
        try:
            self.session.add_all(objs)
            if commit:
                self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error batch creating {self.model.__name__}: {e}")
            if commit:
                self.session.rollback()
            return False

    def update(self, obj: T, commit: bool = True) -> Optional[T]:
        """更新对象

        Args:
            obj: 要更新的对象（必须已在Session中）
            commit: 是否立即提交

        Returns:
            更新后的对象，失败返回None
        """
        try:
            self.session.merge(obj)
            if commit:
                self.session.commit()
                self.session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model.__name__}: {e}")
            if commit:
                self.session.rollback()
            return None

    def delete(self, obj: T, commit: bool = True) -> bool:
        """删除对象

        Args:
            obj: 要删除的对象
            commit: 是否立即提交

        Returns:
            成功返回True
        """
        try:
            self.session.delete(obj)
            if commit:
                self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model.__name__}: {e}")
            if commit:
                self.session.rollback()
            return False

    def delete_by_id(self, id_value: Any, commit: bool = True) -> bool:
        """根据主键删除对象

        Args:
            id_value: 主键值
            commit: 是否立即提交

        Returns:
            成功返回True
        """
        obj = self.get_by_id(id_value)
        if obj:
            return self.delete(obj, commit=commit)
        return False

    def commit(self):
        """提交事务"""
        try:
            self.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error committing: {e}")
            self.session.rollback()
            raise

    def rollback(self):
        """回滚事务"""
        self.session.rollback()

    def flush(self):
        """刷新到数据库（不提交）"""
        try:
            self.session.flush()
        except SQLAlchemyError as e:
            logger.error(f"Error flushing: {e}")
            self.session.rollback()
            raise
