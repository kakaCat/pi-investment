"""
JWT 认证管理器

提供 JWT Token 生成、验证、刷新功能
"""
import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, jsonify

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
            secret_key: JWT 签名密钥（从环境变量 JWT_SECRET_KEY 读取）
            algorithm: 加密算法，默认 HS256
            access_token_expires: Access Token 过期时间（秒），默认 1 小时
            refresh_token_expires: Refresh Token 过期时间（秒），默认 7 天
        """
        self.secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")

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


# ── Flask 装饰器 ──

def require_auth(f):
    """Flask 装饰器：要求 JWT 认证

    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_endpoint():
            # request.user_id 和 request.username 可用
            return jsonify({'message': 'Protected data'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从 Authorization header 获取 token
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({
                "success": False,
                "error": "Missing Authorization header"
            }), 401

        # 解析 "Bearer <token>" 格式
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "success": False,
                "error": "Invalid Authorization header format. Use: Bearer <token>"
            }), 401

        token = parts[1]

        # 验证 token
        jwt_manager = get_jwt_manager()
        try:
            payload = jwt_manager.verify_token(token)

            # 将用户信息附加到 request 对象
            request.user_id = payload["user_id"]
            request.username = payload["username"]
            request.token_payload = payload

            return f(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "Token expired"
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "Invalid token"
            }), 401

    return decorated_function


def require_roles(*required_roles):
    """Flask 装饰器：要求特定角色

    Usage:
        @app.route('/api/admin')
        @require_auth
        @require_roles('admin')
        def admin_endpoint():
            return jsonify({'message': 'Admin only'})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 需要先通过 @require_auth
            if not hasattr(request, 'token_payload'):
                return jsonify({
                    "success": False,
                    "error": "Authentication required"
                }), 401

            user_roles = request.token_payload.get("roles", [])

            # 检查是否有任一所需角色
            if not any(role in user_roles for role in required_roles):
                return jsonify({
                    "success": False,
                    "error": f"Required roles: {', '.join(required_roles)}"
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator
