"""
Command Registry

命令注册表，负责命令的注册、发现和调度。
"""

from typing import Dict, List, Optional, Type
from .command_base import Command


class CommandRegistry:
    """命令注册表"""

    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._domains: Dict[str, List[str]] = {}

    def register(self, command: Command) -> None:
        """
        注册命令

        Args:
            command: 命令实例
        """
        name = command.name
        if name in self._commands:
            raise ValueError(f"命令已存在: {name}")

        self._commands[name] = command

        # 更新域索引
        domain = command.domain
        if domain not in self._domains:
            self._domains[domain] = []
        self._domains[domain].append(name)

    def get(self, name: str) -> Optional[Command]:
        """
        获取命令

        Args:
            name: 命令名称 (如 'stock.search')

        Returns:
            Command实例，不存在返回None
        """
        return self._commands.get(name)

    def list_all(self) -> List[Command]:
        """列出所有命令"""
        return list(self._commands.values())

    def list_by_domain(self, domain: str) -> List[Command]:
        """
        列出指定域的所有命令

        Args:
            domain: 域名 (如 'stock')

        Returns:
            命令列表
        """
        command_names = self._domains.get(domain, [])
        return [self._commands[name] for name in command_names]

    def get_domains(self) -> List[str]:
        """获取所有域"""
        return sorted(self._domains.keys())

    def exists(self, name: str) -> bool:
        """检查命令是否存在"""
        return name in self._commands

    def count(self) -> int:
        """获取命令总数"""
        return len(self._commands)

    def clear(self) -> None:
        """清空注册表"""
        self._commands.clear()
        self._domains.clear()


# 全局注册表实例
_global_registry = CommandRegistry()


def get_registry() -> CommandRegistry:
    """获取全局注册表"""
    return _global_registry


def register_command(command: Command) -> None:
    """注册命令到全局注册表"""
    _global_registry.register(command)


def auto_discover_commands(http_client) -> CommandRegistry:
    """
    自动发现并注册所有命令

    Args:
        http_client: HTTP客户端实例

    Returns:
        CommandRegistry: 注册表实例
    """
    from .commands import stock_commands, market_commands, kline_commands
    from .commands import factor_commands, signal_commands, strategy_commands
    from .commands import indicator_commands

    registry = CommandRegistry()

    # 注册Stock命令
    for cmd_class in stock_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Market命令
    for cmd_class in market_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Kline命令
    for cmd_class in kline_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Factor命令
    for cmd_class in factor_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Signal命令
    for cmd_class in signal_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    # 注册Strategy命令（不需要http_client）
    for cmd_class in strategy_commands.get_all_commands():
        registry.register(cmd_class())

    # 注册Indicator命令
    for cmd_class in indicator_commands.get_all_commands():
        registry.register(cmd_class(http_client))

    return registry
