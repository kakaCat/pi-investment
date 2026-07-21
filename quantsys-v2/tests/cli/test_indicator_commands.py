"""
Tests for Indicator Commands

测试指标命令的基础结构和参数验证
"""

import pytest
from unittest.mock import Mock
from adapters.inbound.cli.commands.indicator_commands import (
    IndicatorListCommand,
    IndicatorCreateCommand,
    IndicatorUpdateCommand,
    IndicatorRunCommand,
    IndicatorBacktestCommand,
    get_all_commands
)


def test_indicator_list_command_exists():
    """测试 IndicatorListCommand 类存在且可实例化"""
    mock_client = Mock()
    cmd = IndicatorListCommand(mock_client)

    assert cmd.name == "indicators.list"
    assert cmd.description is not None
    assert cmd.get_endpoint() == "/api/indicators"
    assert cmd.get_method() == "GET"


def test_indicator_create_command_validation():
    """测试创建指标命令的参数验证"""
    mock_client = Mock()
    cmd = IndicatorCreateCommand(mock_client)

    # 缺少 name 参数
    error = cmd.validate_params(code="print('test')")
    assert error is not None
    assert "name" in error.lower()

    # 缺少 code 参数
    error = cmd.validate_params(name="test_indicator")
    assert error is not None
    assert "code" in error.lower()

    # 参数完整
    error = cmd.validate_params(name="test_indicator", code="print('test')")
    assert error is None


def test_indicator_update_command_validation():
    """测试更新指标命令的参数验证"""
    mock_client = Mock()
    cmd = IndicatorUpdateCommand(mock_client)

    # 缺少 indicator_id 参数
    error = cmd.validate_params(name="new_name")
    assert error is not None
    assert "indicator_id" in error.lower()

    # 参数完整
    error = cmd.validate_params(indicator_id="123", name="new_name")
    assert error is None


def test_indicator_run_command_validation():
    """测试运行指标命令的参数验证"""
    mock_client = Mock()
    cmd = IndicatorRunCommand(mock_client)

    # 缺少 indicator_id 参数
    error = cmd.validate_params(symbol="000001.SH")
    assert error is not None
    assert "indicator_id" in error.lower()

    # 缺少 symbol 参数
    error = cmd.validate_params(indicator_id="123")
    assert error is not None
    assert "symbol" in error.lower()

    # 参数完整
    error = cmd.validate_params(indicator_id="123", symbol="000001.SH")
    assert error is None


def test_indicator_backtest_command_validation():
    """测试回测指标命令的参数验证"""
    mock_client = Mock()
    cmd = IndicatorBacktestCommand(mock_client)

    # 缺少 indicator_id 参数
    error = cmd.validate_params(symbol="000001.SH", start_date="2024-01-01")
    assert error is not None
    assert "indicator_id" in error.lower()

    # 缺少 symbol 参数
    error = cmd.validate_params(indicator_id="123", start_date="2024-01-01")
    assert error is not None
    assert "symbol" in error.lower()

    # 缺少 start_date 参数
    error = cmd.validate_params(indicator_id="123", symbol="000001.SH")
    assert error is not None
    assert "start_date" in error.lower()

    # 参数完整
    error = cmd.validate_params(
        indicator_id="123",
        symbol="000001.SH",
        start_date="2024-01-01"
    )
    assert error is None


def test_get_all_commands():
    """测试 get_all_commands 函数返回所有命令类"""
    commands = get_all_commands()

    assert len(commands) == 5
    assert IndicatorListCommand in commands
    assert IndicatorCreateCommand in commands
    assert IndicatorUpdateCommand in commands
    assert IndicatorRunCommand in commands
    assert IndicatorBacktestCommand in commands


def test_file_reading_with_context_manager():
    """测试文件读取使用 with 语句（资源泄漏修复）"""
    import tempfile
    import os
    from adapters.inbound.cli.commands.indicator_commands import _read_code_file

    # 创建临时 Python 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def test():\n    return 42')
        temp_file = f.name

    try:
        # 读取文件
        content = _read_code_file(temp_file)
        assert 'def test():' in content
        assert 'return 42' in content
    finally:
        os.unlink(temp_file)


def test_path_traversal_protection():
    """测试路径遍历攻击防护"""
    from adapters.inbound.cli.commands.indicator_commands import _read_code_file

    # 尝试访问上级目录（路径遍历攻击）
    try:
        _read_code_file('../../../../etc/passwd')
        assert False, "应该抛出 ValueError"
    except (ValueError, FileNotFoundError) as e:
        # 可能是 ValueError（路径不安全）或 FileNotFoundError（文件不存在）
        assert "文件路径不安全" in str(e) or "不存在" in str(e)


def test_non_python_file_rejection():
    """测试非 Python 文件被拒绝"""
    import tempfile
    import os
    from adapters.inbound.cli.commands.indicator_commands import _read_code_file

    # 创建非 .py 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('malicious content')
        temp_file = f.name

    try:
        _read_code_file(temp_file)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "必须是 .py 文件" in str(e)
    finally:
        os.unlink(temp_file)


def test_instance_variable_cleanup():
    """测试实例变量在执行后被清理（防止状态泄漏）"""
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.request = Mock(return_value={'success': True, 'data': {}})

    cmd = IndicatorUpdateCommand(mock_client)

    # 第一次执行
    result1 = cmd.execute(indicator_id='id1', name='test1')
    assert result1.success

    # 验证状态被清理
    assert cmd._current_indicator_id is None

    # 第二次执行不同的 ID
    result2 = cmd.execute(indicator_id='id2', name='test2')
    assert result2.success

    # 验证状态再次被清理
    assert cmd._current_indicator_id is None

