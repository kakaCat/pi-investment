"""loop_supervisor 核心逻辑测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loop_supervisor import next_backoff, should_restart, PROCESSES


def test_backoff_sequence():
    """指数退避：1min → 5min → 15min 封顶"""
    assert next_backoff(1) == 60
    assert next_backoff(2) == 300
    assert next_backoff(3) == 900
    assert next_backoff(10) == 900  # 封顶


def test_should_restart_after_three_health_failures():
    assert should_restart(consecutive_health_failures=2, process_alive=True) is False
    assert should_restart(consecutive_health_failures=3, process_alive=True) is True
    assert should_restart(consecutive_health_failures=0, process_alive=False) is True


def test_process_config_integrity():
    """4 个进程配置完整：启动顺序、命令、健康检查"""
    assert [p['name'] for p in PROCESSES] == [
        'v2-api', 'v2-daemon', 'agent-dev', 'agent-wake']
    for p in PROCESSES:
        assert p['cmd'], f"{p['name']} 缺少启动命令"
        assert p['cwd'], f"{p['name']} 缺少工作目录"
        assert p['health']['type'] in ('http', 'process'), f"{p['name']} 健康检查类型非法"
    # v2-api 必须先于依赖它的进程
    assert PROCESSES[0]['name'] == 'v2-api'
    # daemon 必须用 venv python（monotonic/misfire 坑）
    assert 'venv' in PROCESSES[1]['cmd'][0]
    # wake channel 健康检查指向 3002 固定端口
    assert '3002' in PROCESSES[3]['health']['url']
