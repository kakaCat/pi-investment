"""BaostockKlineProvider 会话失效重登测试（2026-08-02）

背景：回填进程跑到一半 baostock 会话被并发打断（broken pipe）后，后续几千只
股票全部「网络接收错误」——provider 缓存会话从不重登。修复：会话级错误时
重置会话并重试一次。
"""
from unittest.mock import MagicMock

from adapters.outbound.datasources.providers.kline.baostock import BaostockKlineProvider


def _ok_rs(rows):
    rs = MagicMock()
    rs.error_code = '0'
    rs.error_msg = 'success'
    rs.next = MagicMock(side_effect=[True] * len(rows) + [False])
    rs.get_row_data = MagicMock(side_effect=rows)
    return rs


def _err_rs(msg):
    rs = MagicMock()
    rs.error_code = '-10003005'
    rs.error_msg = msg
    return rs


_ROW = ['2026-07-31', 'sh.600000', '9.5', '9.6', '9.4', '9.51', '1000000', '9500000.0', '0.5']


class TestSessionRecovery:
    def test_session_error_resets_and_retries(self):
        provider = BaostockKlineProvider()
        bs = MagicMock()
        # 第一次查询会话失效，第二次成功
        bs.query_history_k_data_plus = MagicMock(side_effect=[
            _err_rs('网络接收错误。'),
            _ok_rs([_ROW]),
        ])
        provider._bs = bs  # 假装已登录
        reset_calls = []
        provider._reset_session = lambda: reset_calls.append(1)

        result = provider.get_klines('600000', 'daily', '2026-07-28', '2026-07-31')

        assert result is not None and len(result) == 1
        assert result[0].close == 9.51
        assert len(reset_calls) == 1
        assert bs.query_history_k_data_plus.call_count == 2

    def test_permanent_error_no_retry(self):
        """代码类错误（如北交所不支持）不是会话问题，不应重试"""
        provider = BaostockKlineProvider()
        bs = MagicMock()
        bs.query_history_k_data_plus = MagicMock(return_value=_err_rs('股票代码未标识sh或sz'))
        provider._bs = bs
        reset_calls = []
        provider._reset_session = lambda: reset_calls.append(1)

        result = provider.get_klines('810011', 'daily', '2026-07-28', '2026-07-31')

        assert result is None
        assert len(reset_calls) == 0
        assert bs.query_history_k_data_plus.call_count == 1

    def test_no_data_no_retry(self):
        """正常空结果（退市/停牌）不是会话问题，不应重试"""
        provider = BaostockKlineProvider()
        bs = MagicMock()
        bs.query_history_k_data_plus = MagicMock(return_value=_ok_rs([]))
        provider._bs = bs
        reset_calls = []
        provider._reset_session = lambda: reset_calls.append(1)

        result = provider.get_klines('600068', 'daily', '2026-07-28', '2026-07-31')

        assert result is None
        assert len(reset_calls) == 0

    def test_exception_level_session_error_retries(self):
        """连接异常（Broken pipe 等抛异常形态）也应重置重试"""
        provider = BaostockKlineProvider()
        bs = MagicMock()
        bs.query_history_k_data_plus = MagicMock(side_effect=[
            ConnectionError('Broken pipe'),
            _ok_rs([_ROW]),
        ])
        provider._bs = bs
        reset_calls = []
        provider._reset_session = lambda: reset_calls.append(1)

        result = provider.get_klines('600000', 'daily', '2026-07-28', '2026-07-31')

        assert result is not None
        assert len(reset_calls) == 1


def test_socket_watchdog_interrupts_blackhole():
    """看门狗：socket 黑洞（对端不应答）时 baostock 调用必须在超时后抛错而非永久阻塞

    2026-08-05 根因：baostock 库 socket 无超时，IP 被封黑洞时 recv 永久阻塞，
    评分线程池 worker 全灭（/api/signals/scan 反复调用后挂死）。
    """
    import socket
    import time
    import baostock.common.context as bs_context
    from adapters.outbound.datasources.providers.kline.baostock import _with_socket_timeout

    # 本地回环模拟黑洞：连接成功但对端永不 send
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen(1)
    sock = socket.socket()
    sock.connect(('127.0.0.1', srv.getsockname()[1]))
    bs_context.default_socket = sock

    t0 = time.time()
    try:
        _with_socket_timeout(lambda: sock.recv(10), timeout=1)
        raise AssertionError('黑洞调用未被看门狗打断')
    except OSError:
        pass  # 预期：看门狗关闭 socket 使 recv 抛错
    finally:
        srv.close()
        if hasattr(bs_context, 'default_socket'):
            delattr(bs_context, 'default_socket')

    assert time.time() - t0 < 5, '看门狗未及时打断阻塞调用'
