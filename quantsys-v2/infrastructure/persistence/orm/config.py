"""
ORM配置模块 - 管理SQLAlchemy ORM的全局Session和Base

本模块提供：
1. declarative_base() - 所有Model的基类
2. scoped_session - 线程级Session管理（自动清理，避免连接泄漏）
3. init_orm() - 应用启动时初始化
4. get_session() - 获取当前线程的Session
"""
# 首先加载环境变量
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件（如果存在）
_env_file = Path(__file__).parent.parent.parent.parent / '.env'
if _env_file.exists():
    load_dotenv(_env_file, override=False)

import logging
from typing import Optional, Tuple
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import scoped_session, sessionmaker, Session, declarative_base

logger = logging.getLogger(__name__)

# 全局Base类 - 所有Model继承此类
Base = declarative_base()

# 全局变量
_engine: Optional[Engine] = None
_SessionFactory: Optional[scoped_session] = None
_orm_initialized = False


def init_orm(
    dsn: Optional[str] = None,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    echo: bool = False
) -> Tuple[Engine, scoped_session]:
    """初始化ORM（应用启动时调用一次）

    Args:
        dsn: 数据库连接字符串，None则从环境变量读取
        pool_size: 连接池保持的常驻连接数
        max_overflow: 超过pool_size时允许的临时连接数
        pool_pre_ping: 连接取出前先ping，坏连接自动移除
        pool_recycle: 连接回收时间（秒），防止DB端超时断开
        echo: 是否打印SQL日志（调试用）

    Returns:
        (engine, SessionFactory) 元组

    Raises:
        RuntimeError: 数据库配置不存在时
    """
    global _engine, _SessionFactory, _orm_initialized

    if _orm_initialized:
        logger.info("ORM already initialized, skipping")
        return _engine, _SessionFactory

    # 解析DSN
    if dsn is None:
        from infrastructure.persistence.database.engine import _resolve_db_dsn
        dsn = _resolve_db_dsn()

    if not dsn:
        raise RuntimeError(
            "No database DSN configured. "
            "Set QUANT_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN."
        )

    # 创建Engine
    # 注意：sqlite（测试/开发常用）的默认 Pool 不支持 pool_size/max_overflow，
    # 仅对支持连接池参数的数据库传递这些参数
    engine_kwargs = {
        "pool_pre_ping": pool_pre_ping,
        "pool_recycle": pool_recycle,
        "echo": echo,
    }
    if not dsn.startswith("sqlite"):
        engine_kwargs["pool_size"] = pool_size
        engine_kwargs["max_overflow"] = max_overflow

    _engine = create_engine(dsn, **engine_kwargs)

    # 创建scoped_session工厂
    # scoped_session特性：
    # 1. 每个线程自动获得独立的Session
    # 2. 同一线程多次调用get_session()返回同一个Session
    # 3. 调用remove()后会自动关闭Session并清理资源
    session_factory = sessionmaker(bind=_engine)
    _SessionFactory = scoped_session(session_factory)

    _orm_initialized = True
    logger.info(
        f"ORM initialized: pool_size={pool_size}, "
        f"max_overflow={max_overflow}, echo={echo}"
    )

    # 注册退出时清理
    import atexit
    atexit.register(close_orm)

    return _engine, _SessionFactory


def get_session() -> Session:
    """获取当前线程的Session

    特性：
    - 同一线程内多次调用返回同一个Session
    - 不同线程自动获得不同的Session
    - 使用完毕后应调用close_session()清理

    Returns:
        当前线程的Session实例

    Raises:
        RuntimeError: ORM未初始化时
    """
    if _SessionFactory is None:
        # 自动初始化（便于开发，生产环境应显式init）
        logger.warning("ORM not initialized, auto-initializing...")
        init_orm()

    return _SessionFactory()


def close_session():
    """关闭当前线程的Session

    调用时机：
    1. 请求结束时（Flask/FastAPI的teardown）
    2. Job执行完毕时
    3. 脚本退出前

    效果：
    - 提交未完成的事务
    - 关闭数据库连接（归还连接池）
    - 清理Session状态
    """
    if _SessionFactory:
        _SessionFactory.remove()


def register_session_teardown(app) -> None:
    """注册 Flask teardown 钩子：每个请求结束时自动调用 close_session()

    背景：scoped_session 懒加载的 Session 在首个查询后开启事务并持有连接，
    若请求结束不清理，连接将以 "idle in transaction" 状态被该线程长期占用，
    连接池（pool_size + max_overflow）耗尽后，新请求会阻塞至 pool_timeout
    （SQLAlchemy 默认 30s），表现为接口随机卡顿约 30 秒。

    用法：在 Flask create_app() 中 init_orm() 之后调用一次：
        init_orm(pool_size=10, max_overflow=20)
        register_session_teardown(app)
    """
    @app.teardown_appcontext
    def _remove_session_on_teardown(exception=None):
        close_session()


def close_orm():
    """关闭ORM（进程退出时调用）"""
    global _engine, _SessionFactory, _orm_initialized

    if _SessionFactory:
        _SessionFactory.remove()
        _SessionFactory = None

    if _engine:
        try:
            _engine.dispose()
            logger.info("ORM engine disposed")
        except Exception as e:
            logger.error(f"Error disposing ORM engine: {e}")
        finally:
            _engine = None

    _orm_initialized = False


def get_engine() -> Optional[Engine]:
    """获取Engine实例（用于原生SQL执行）"""
    return _engine


def is_initialized() -> bool:
    """检查ORM是否已初始化"""
    return _orm_initialized
