"""Method registry for daemon handlers."""
from typing import Callable, Dict, List, Optional
import inspect


class MethodRegistry:
    """Registry for JSON-RPC method handlers."""

    def __init__(self):
        """Initialize empty registry."""
        self._handlers: Dict[str, Callable] = {}

    def register(self, method_name: str, handler: Callable) -> None:
        """
        Register a method handler.

        Args:
            method_name: JSON-RPC method name
            handler: Async function that takes params dict and returns JSON string

        Raises:
            ValueError: If method already registered or handler invalid
        """
        if method_name in self._handlers:
            raise ValueError(f"Method '{method_name}' already registered")

        if not inspect.iscoroutinefunction(handler):
            raise ValueError(f"Handler for '{method_name}' must be async function")

        self._handlers[method_name] = handler

    def has_method(self, method_name: str) -> bool:
        """Check if method is registered."""
        return method_name in self._handlers

    def get_handler(self, method_name: str) -> Optional[Callable]:
        """Get handler for method, or None if not found."""
        return self._handlers.get(method_name)

    def list_methods(self) -> List[str]:
        """List all registered method names."""
        return list(self._handlers.keys())


# Global registry instance
_global_registry = MethodRegistry()


def register_method(method_name: str, registry: Optional[MethodRegistry] = None):
    """
    Decorator to register a method handler.

    Args:
        method_name: JSON-RPC method name
        registry: Registry instance (uses global if None)

    Example:
        @register_method("get_stock_info")
        async def get_stock_info(params: dict) -> str:
            return json.dumps({"result": "data"})
    """
    target_registry = registry if registry is not None else _global_registry

    def decorator(func: Callable) -> Callable:
        target_registry.register(method_name, func)
        return func

    return decorator


def get_global_registry() -> MethodRegistry:
    """Get the global registry instance."""
    return _global_registry
