"""业务异常层次结构

使用方式:
    # 路由层捕获特定异常返回对应 HTTP 状态码
    try:
        service.do_something()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
"""


class DomainError(Exception):
    """领域层基础异常"""
    pass


class NotFoundError(DomainError):
    """资源不存在"""
    pass


class ValidationError(DomainError):
    """参数校验失败"""
    pass


class ConflictError(DomainError):
    """资源冲突（如重复创建）"""
    pass


class ExternalServiceError(DomainError):
    """外部服务调用失败（akshare/eastmoney 等）"""
    pass


class DatabaseError(DomainError):
    """数据库操作失败"""
    pass


class AuthenticationError(DomainError):
    """认证失败"""
    pass


class AuthorizationError(DomainError):
    """权限不足"""
    pass
