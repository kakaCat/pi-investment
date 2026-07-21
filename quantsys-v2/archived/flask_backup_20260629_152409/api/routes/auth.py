"""
认证路由 - 登录、注册、Token 刷新

提供 JWT 认证的 API 端点
"""
from flask import Blueprint, request, jsonify
import logging

from infrastructure.auth import (
    get_jwt_manager,
    limit_login,
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
@limit_login
def login():
    """用户登录

    Request:
        {
            "username": "admin",
            "password": "password"
        }

    Response:
        {
            "success": true,
            "data": {
                "access_token": "eyJ...",
                "refresh_token": "eyJ...",
                "expires_in": 3600,
                "user": {
                    "user_id": 1,
                    "username": "admin",
                    "roles": ["admin"]
                }
            }
        }
    """
    try:
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({
                "success": False,
                "error": "Username and password required"
            }), 400

        # TODO: 实际验证逻辑（查询数据库、验证密码）
        # 这里暂时使用硬编码演示
        if username == "admin" and password == "admin123":
            user_id = 1
            roles = ["admin", "user"]
        elif username == "user" and password == "user123":
            user_id = 2
            roles = ["user"]
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            return jsonify({
                "success": False,
                "error": "Invalid credentials"
            }), 401

        # 生成 JWT Token
        jwt_manager = get_jwt_manager()
        access_token = jwt_manager.generate_token(
            user_id=user_id,
            username=username,
            token_type="access",
            roles=roles
        )
        refresh_token = jwt_manager.generate_token(
            user_id=user_id,
            username=username,
            token_type="refresh",
            roles=roles
        )

        logger.info(f"User {username} logged in successfully")

        return jsonify({
            "success": True,
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": jwt_manager.access_token_expires,
                "user": {
                    "user_id": user_id,
                    "username": username,
                    "roles": roles
                }
            }
        }), 200

    except Exception as e:
        logger.exception("Login error")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@auth_bp.route("/api/auth/refresh", methods=["POST"])
def refresh_token():
    """刷新 Access Token

    Request:
        {
            "refresh_token": "eyJ..."
        }

    Response:
        {
            "success": true,
            "data": {
                "access_token": "eyJ...",
                "expires_in": 3600
            }
        }
    """
    try:
        data = request.get_json() or {}
        refresh_token = data.get("refresh_token")

        if not refresh_token:
            return jsonify({
                "success": False,
                "error": "Refresh token required"
            }), 400

        jwt_manager = get_jwt_manager()
        new_access_token = jwt_manager.refresh_access_token(refresh_token)

        if not new_access_token:
            return jsonify({
                "success": False,
                "error": "Invalid or expired refresh token"
            }), 401

        return jsonify({
            "success": True,
            "data": {
                "access_token": new_access_token,
                "expires_in": jwt_manager.access_token_expires
            }
        }), 200

    except Exception as e:
        logger.exception("Token refresh error")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@auth_bp.route("/api/auth/verify", methods=["GET"])
def verify_token():
    """验证 Token 是否有效

    Headers:
        Authorization: Bearer <token>

    Response:
        {
            "success": true,
            "data": {
                "valid": true,
                "user": {
                    "user_id": 1,
                    "username": "admin"
                }
            }
        }
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return jsonify({
            "success": False,
            "error": "Missing Authorization header"
        }), 401

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({
            "success": False,
            "error": "Invalid Authorization header format"
        }), 401

    token = parts[1]

    try:
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.verify_token(token)

        return jsonify({
            "success": True,
            "data": {
                "valid": True,
                "user": {
                    "user_id": payload["user_id"],
                    "username": payload["username"],
                    "roles": payload.get("roles", [])
                }
            }
        }), 200

    except Exception:
        return jsonify({
            "success": False,
            "data": {
                "valid": False
            }
        }), 401
