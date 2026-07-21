"""Tests for method registry."""
import pytest
from infrastructure.daemon.registry import MethodRegistry, register_method


@pytest.fixture
def registry():
    """Create fresh registry for each test."""
    return MethodRegistry()


def test_register_method_decorator(registry):
    """Test registering method with decorator."""
    @register_method("test_method", registry=registry)
    async def test_handler(params: dict) -> str:
        return "test_result"

    assert registry.has_method("test_method")
    handler = registry.get_handler("test_method")
    assert handler is not None


def test_get_handler_not_found(registry):
    """Test getting non-existent handler."""
    handler = registry.get_handler("nonexistent")
    assert handler is None


def test_register_duplicate_method(registry):
    """Test registering duplicate method raises error."""
    @register_method("duplicate", registry=registry)
    async def handler1(params: dict) -> str:
        return "first"

    with pytest.raises(ValueError) as exc_info:
        @register_method("duplicate", registry=registry)
        async def handler2(params: dict) -> str:
            return "second"

    assert "already registered" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_handler(registry):
    """Test calling registered handler."""
    @register_method("echo", registry=registry)
    async def echo_handler(params: dict) -> str:
        return params.get("message", "")

    handler = registry.get_handler("echo")
    result = await handler({"message": "hello"})
    assert result == "hello"


def test_register_non_async_handler(registry):
    """Test registering non-async handler raises error."""
    def sync_handler(params: dict) -> str:
        return "sync"

    with pytest.raises(ValueError) as exc_info:
        registry.register("sync_method", sync_handler)

    assert "must be async function" in str(exc_info.value)


def test_list_methods(registry):
    """Test listing registered methods."""
    assert registry.list_methods() == []

    @register_method("method1", registry=registry)
    async def handler1(params: dict) -> str:
        return "result1"

    @register_method("method2", registry=registry)
    async def handler2(params: dict) -> str:
        return "result2"

    methods = registry.list_methods()
    assert len(methods) == 2
    assert "method1" in methods
    assert "method2" in methods


def test_global_registry():
    """Test global registry access."""
    from infrastructure.daemon.registry import get_global_registry

    registry = get_global_registry()
    assert isinstance(registry, MethodRegistry)
