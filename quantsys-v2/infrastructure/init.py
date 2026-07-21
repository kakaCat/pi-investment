"""
应用初始化模块

在应用启动时初始化ORM和其他核心组件

使用方式：
    from infrastructure.init import init_application

    # 应用启动时调用
    init_application()
"""
import logging
from infrastructure.persistence.orm import init_orm

logger = logging.getLogger(__name__)


def init_application():
    """初始化应用

    包括：
    1. 初始化ORM
    2. 其他初始化任务
    """
    try:
        # 初始化ORM
        logger.info("正在初始化ORM...")
        init_orm(echo=False)
        logger.info("✅ ORM初始化成功")

        # 其他初始化任务可以在这里添加

        return True
    except Exception as e:
        logger.error(f"❌ 应用初始化失败: {e}")
        return False


__all__ = ['init_application']
