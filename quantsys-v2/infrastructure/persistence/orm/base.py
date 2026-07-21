"""
ORM基础配置
"""
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class TimestampMixin:
    """时间戳Mixin - 自动添加created_at和updated_at字段"""
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


def to_dict(obj):
    """将ORM对象转换为字典"""
    if obj is None:
        return None

    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        # 处理datetime类型
        if isinstance(value, datetime):
            value = value.isoformat()
        result[column.name] = value
    return result
