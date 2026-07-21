"""
异步ORM基础Repository - 提供通用CRUD操作

所有异步Repository应继承此类
"""
import logging
from typing import TypeVar, Generic, Optional, List, Type, Any, Dict
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)


class AsyncBaseORMRepository(Generic[T]):
    """异步ORM Repository基类

    Usage:
        class StockPoolAsyncRepository(AsyncBaseORMRepository[StockPool]):
            model = StockPool

            async def find_by_name(self, name: str) -> Optional[StockPool]:
                stmt = select(self.model).where(self.model.name == name)
                result = await self.session.execute(stmt)
                return result.scalars().first()
    """

    model: Type[T] = None  # 子类必须设置

    def __init__(self, session: AsyncSession):
        """初始化Repository

        Args:
            session: 异步Session实例（通常通过依赖注入获得）
        """
        if self.model is None:
            raise ValueError(f"{self.__class__.__name__} must define 'model' class attribute")
        self.session = session

    async def get_by_id(self, id_value: Any) -> Optional[T]:
        """根据ID查询单条记录

        Args:
            id_value: 主键值

        Returns:
            Model实例或None
        """
        try:
            result = await self.session.get(self.model, id_value)
            return result
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} by id {id_value}: {e}")
            return None

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """列出所有记录（带分页）

        Args:
            limit: 返回条数
            offset: 偏移量

        Returns:
            Model实例列表
        """
        try:
            stmt = select(self.model).limit(limit).offset(offset)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error listing {self.model.__name__}: {e}")
            return []

    async def find_by_condition(self, **conditions) -> List[T]:
        """根据条件查询多条记录

        Args:
            **conditions: 字段名=值的键值对

        Returns:
            Model实例列表

        Example:
            pools = await repo.find_by_condition(pool_type='dynamic', status='active')
        """
        try:
            stmt = select(self.model)
            for field, value in conditions.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error finding {self.model.__name__} by conditions {conditions}: {e}")
            return []

    async def find_one_by_condition(self, **conditions) -> Optional[T]:
        """根据条件查询单条记录

        Args:
            **conditions: 字段名=值的键值对

        Returns:
            Model实例或None
        """
        try:
            stmt = select(self.model)
            for field, value in conditions.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

            result = await self.session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error finding one {self.model.__name__} by conditions {conditions}: {e}")
            return None

    async def create(self, data: Dict[str, Any]) -> Optional[T]:
        """创建记录

        Args:
            data: 字段名=值的字典

        Returns:
            创建的Model实例或None
        """
        try:
            instance = self.model(**data)
            self.session.add(instance)
            await self.session.flush()  # 刷新以获得ID等自动生成字段
            await self.session.refresh(instance)
            return instance
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            await self.session.rollback()
            return None

    async def update_by_id(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """根据ID更新记录

        Args:
            id_value: 主键值
            data: 要更新的字段字典

        Returns:
            是否成功
        """
        try:
            stmt = (
                update(self.model)
                .where(self.model.id == id_value)
                .values(**data)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} id {id_value}: {e}")
            await self.session.rollback()
            return False

    async def delete_by_id(self, id_value: Any) -> bool:
        """根据ID删除记录

        Args:
            id_value: 主键值

        Returns:
            是否成功
        """
        try:
            stmt = delete(self.model).where(self.model.id == id_value)
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__} id {id_value}: {e}")
            await self.session.rollback()
            return False

    async def count(self, **conditions) -> int:
        """统计记录数

        Args:
            **conditions: 可选的过滤条件

        Returns:
            记录数
        """
        try:
            from sqlalchemy import func
            stmt = select(func.count()).select_from(self.model)

            for field, value in conditions.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

            result = await self.session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            return 0

    async def exists(self, **conditions) -> bool:
        """检查记录是否存在

        Args:
            **conditions: 过滤条件

        Returns:
            是否存在
        """
        count = await self.count(**conditions)
        return count > 0


__all__ = ['AsyncBaseORMRepository']
