"""
依赖注入容器模块

提供企业级依赖注入，替代全局变量和懒加载反模式。

注意：暂时不自动导入 Container，因为它有类型注解问题。
使用 SimpleContainer 作为过渡方案。
"""

# 不自动导入 Container，避免类型注解错误
# from .container import Container

__all__ = []  # 暂时为空，需要时手动导入
