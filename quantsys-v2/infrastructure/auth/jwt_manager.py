"""
JWT 认证管理器

提供 JWT Token 生成、验证、刷新功能
"""
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
from infrastructure.config import get_config

logger = logging.getLogger(__name__)


class JWTManager:
    """JWT 认证管理器

    Usage:
        # 初始化
        jwt_manager = JWTManager(secret_key="your-secret")

        # 生成 Token
        token = jwt_manager.generate_token(user_id=123, username="admin")

        # 验证 Token
        payload = jwt_manager.verify_token(token)
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expires: int = 3600,  # 1 hour
        refresh_token_expires: int = 604800,  # 7 days
    ):
        """初始化 JWT 管理器

        Args:
            secret_key: JWT 签名密钥（从配置读取）
            algorithm: 加密算法，默认 HS256
            access_token_expires: Access Token 过期时间（秒），默认 1 小时
            refresh_token_expires: Refresh Token 过期时间（秒），默认 7 天
        """
        config = get_config()
        self.secret_key = secret_key or config.app.jwt_secret_key

        if not self.secret_key:
            logger.warning(
                "JWT_SECRET_KEY not configured. Using default (INSECURE for production!)"
            )
            self.secret_key = "default-secret-key-change-me-in-production"

        self.algorithm = algorithm
        self.access_token_expires = access_token_expires
        self.refresh_token_expires = refresh_token_expires

    def generate_token(
        self,
        user_id: int,
        username: str,
        token_type: str = "access",
        **extra_claims
    ) -> str:
        """生成 JWT Token

        Args:
            user_id: 用户 ID
            username: 用户名
            token_type: Token 类型（access/refresh）
            **extra_claims: 额外的声明（如 roles, permissions）

        Returns:
            str: JWT Token 字符串

        Example:
            token = jwt_manager.generate_token(
                user_id=123,
                username="admin",
                roles=["admin", "user"]
            )
        """
        now = datetime.utcnow()

        # 根据类型设置过期时间
        if token_type == "refresh":
            expires_delta = timedelta(seconds=self.refresh_token_expires)
        else:
            expires_delta = timedelta(seconds=self.access_token_expires)

        expires = now + expires_delta

        # 构建 payload
        payload = {
            "user_id": user_id,
            "username": username,
            "token_type": token_type,
            "iat": now,  # issued at
            "exp": expires,  # expiration
            **extra_claims
        }

        # 生成 Token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.info(
            f"Generated {token_type} token for user {username} (expires in {expires_delta})"
        )

        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 JWT Token

        Args:
            token: JWT Token 字符串

        Returns:
            dict: Token payload（如果验证成功）
            None: 验证失败

        Raises:
            jwt.ExpiredSignatureError: Token 已过期
            jwt.InvalidTokenError: Token 无效
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """使用 Refresh Token 刷新 Access Token

        Args:
            refresh_token: Refresh Token

        Returns:
            str: 新的 Access Token
            None: 刷新失败
        """
        try:
            payload = self.verify_token(refresh_token)

            # 验证是否为 refresh token
            if payload.get("token_type") != "refresh":
                logger.warning("Invalid token type for refresh")
                return None

            # 生成新的 access token
            new_token = self.generate_token(
                user_id=payload["user_id"],
                username=payload["username"],
                token_type="access"
            )

            return new_token

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None


# ── 全局 JWT 管理器实例 ──

_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    """获取全局 JWT 管理器实例"""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


# ── FastAPI 依赖注入 ──

from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


async def require_auth(credentials: HTTPAuthorizationCredentials = Security(security)):
    """FastAPI 依赖：要求 JWT 认证

    Usage:
        @app.get('/api/protected')
        async def protected_endpoint(user = Depends(require_auth)):
            return {'message': f'Hello {user["username"]}'}
    """
    token = credentials.credentials
    jwt_manager = get_jwt_manager()

    try:
        payload = jwt_manager.verify_token(token)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*required_roles):
    """FastAPI 依赖工厂：要求特定角色

    Usage:
        @app.get('/api/admin')
        async def admin_endpoint(user = Depends(require_roles('admin'))):
            return {'message': 'Admin only'}
    """
    async def role_checker(credentials: HTTPAuthorizationCredentials = Security(security)):
        token = credentials.credentials
        jwt_manager = get_jwt_manager()

        try:
            payload = jwt_manager.verify_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_roles = payload.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Required roles: {', '.join(required_roles)}"
            )

        return payload

    return role_checker
