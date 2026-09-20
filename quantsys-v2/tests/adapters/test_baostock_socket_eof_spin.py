"""baostock 收包循环 EOF 空转修复（2026-09-20）

## 现象与根因

5001 进程（PID 96794）三个线程各 ~58% CPU、合计 ~175%，24h 不停；sys:user = 3.29:1
（77% 时间在内核），socket 零流量。采样栈三个线程完全一致，都是
`method_vectorcall_VARARGS → sock_call_ex → recvfrom`。

真身在第三方库 `baostock/util/socketutil.py:send_msg` 的收包循环：

    receive = b""
    while True:
        recv = default_socket.recv(8192)
        receive += recv
        if receive[-13:] == b"<![CDATA[]]>\\n":
            break

TCP 对端 FIN 之后 `recv()` **立即返回 b""**（永不阻塞），`receive` 恒为 b""，
末 13 字节恒不等于结束标记 → 条件永不成立 → 无限空转。`settimeout` 治不了，
因为根本不存在「等待」。

## 契约

`send_msg` 的调用方（`baostock/security/history.py:106`、`login/loginout.py`）已经写成：

    receive_data = sock.send_msg(...)
    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"

而 `"网络接收错误"` **已在** provider 的 `_SESSION_ERROR_MARKERS` 里 → 现有重登逻辑
接管。所以修法保持上游约定：EOF 时返回 `None`（与既有异常路径同形），绝不空转。
"""
import socket
import time

import pytest

import baostock.common.context as bs_context
from baostock.util import socketutil


class _EofSocket:
    """对端已关闭的 socket：recv 立即返回 b''（TCP FIN 语义）"""

    def __init__(self, max_recv: int = 50):
        self.recv_calls = 0
        self._max_recv = max_recv
        self.closed = False

    def send(self, data):
        return len(data)

    def recv(self, bufsize):
        self.recv_calls += 1
        if self.recv_calls > self._max_recv:
            # 空转检测闸：修复前这里会一路数到百万次、把测试挂死
            raise AssertionError(
                f'EOF 后仍在空转：recv 已被调用 {self.recv_calls} 次')
        return b''

    def shutdown(self, how):
        pass

    def close(self):
        self.closed = True


@pytest.fixture
def using_socket():
    """临时把 bs_context.default_socket 指向伪造 socket，用完还原"""
    def _install(sock):
        bs_context.default_socket = sock
        bs_context.user_id = 'test-user'  # history.py 的前置校验要求已登录
        return sock
    yield _install
    for attr in ('default_socket', 'user_id'):
        if hasattr(bs_context, attr):
            delattr(bs_context, attr)


def test_send_msg_returns_none_on_eof_instead_of_spinning(using_socket):
    """对端 FIN 后必须立刻结束收包，而不是无限 recv 空转

    这是本次修复的核心断言。修复前本用例失败（AssertionError: EOF 后仍在空转）。
    """
    import adapters.outbound.datasources.providers.kline.baostock  # noqa: F401  安装补丁

    sock = using_socket(_EofSocket())

    t0 = time.time()
    result = socketutil.send_msg('query_history_k_data_plus\1user\1...')

    assert result is None, 'EOF 应按上游约定返回 None，交由调用方判为「网络接收错误」'
    assert sock.recv_calls == 1, f'EOF 后不得再 recv，实际 {sock.recv_calls} 次'
    assert time.time() - t0 < 1, 'EOF 处理必须是即时的，不得有可见耗时'


def test_eof_maps_to_session_error_marker_so_provider_relogins(using_socket):
    """EOF 的失败形态必须落在 provider 的重登判定里（闭环验证）"""
    import adapters.outbound.datasources.providers.kline.baostock  # noqa: F401
    from baostock.security import history

    using_socket(_EofSocket())

    rs = history.query_history_k_data_plus(
        'sh.600000', 'date,code,close', start_date='2026-09-01', end_date='2026-09-02')

    assert rs.error_code != '0'
    assert '网络接收错误' in rs.error_msg


def test_normal_response_still_parsed(using_socket):
    """回归：正常应答（未压缩帧）仍被原样解析，补丁不得破坏 happy path"""
    import adapters.outbound.datasources.providers.kline.baostock  # noqa: F401

    payload = '1\1msgtype\1body' + '<![CDATA[]]>\n'

    class _OneShotSocket:
        def send(self, data):
            return len(data)

        def recv(self, bufsize):
            return payload.encode('utf-8')

        def close(self):
            pass

        def shutdown(self, how):
            pass

    using_socket(_OneShotSocket())

    assert socketutil.send_msg('whatever') == payload


def test_watchdog_closes_inflight_socket_even_after_relogin(using_socket):
    """看门狗必须关掉**本次调用实际持有的** socket 对象

    旧实现只关 `bs_context.default_socket` 这个全局引用；一旦重新登录把该全局
    换成新 socket，旧 socket 就再也没人关得掉——被孤立的调用只能永久阻塞/空转
    （这正是三个线程 24h 烧 CPU 的生存机制）。
    """
    import adapters.outbound.datasources.providers.kline.baostock as provider_mod

    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen(1)
    inflight = socket.socket()
    inflight.connect(('127.0.0.1', srv.getsockname()[1]))

    using_socket(inflight)
    provider_mod._register_inflight(inflight)
    try:
        # 模拟「重新登录替换了全局引用」：全局指向另一个 socket，本次调用仍持有 inflight
        decoy = socket.socket()
        bs_context.default_socket = decoy

        t0 = time.time()
        try:
            provider_mod._with_socket_timeout(lambda: inflight.recv(10), timeout=1)
            raise AssertionError('看门狗未能打断本次调用的 socket')
        except OSError:
            pass
        finally:
            decoy.close()
            srv.close()

        assert time.time() - t0 < 5
        assert inflight.fileno() == -1, '看门狗应已关闭本次调用持有的 socket'
    finally:
        provider_mod._clear_inflight(inflight)
        try:
            inflight.close()
        except OSError:
            pass


def test_send_msg_serializes_concurrent_exchanges(using_socket):
    """并发调用必须串行交换，不得在同一 socket 上交叠收发

    同一 provider 单例被评分线程池/回填共用（manager.py 只 new 一个
    BaostockKlineProvider），而 context 里只有一个 default_socket。交叠的收发会
    让 A 线程读到 B 线程的应答，也正是「一个线程 logout 关 socket、另一个线程
    正在 recv」→ EOF 空转的触发路径。
    """
    import adapters.outbound.datasources.providers.kline.baostock  # noqa: F401
    import threading

    payload = 'ok<![CDATA[]]>\n'
    state = {'inflight': 0, 'overlap': 0, 'max_inflight': 0}
    lock = threading.Lock()

    class _SlowSocket:
        def send(self, data):
            return len(data)

        def recv(self, bufsize):
            with lock:
                state['inflight'] += 1
                state['max_inflight'] = max(state['max_inflight'], state['inflight'])
                if state['inflight'] > 1:
                    state['overlap'] += 1
            time.sleep(0.05)
            with lock:
                state['inflight'] -= 1
            return payload.encode('utf-8')

        def close(self):
            pass

        def shutdown(self, how):
            pass

    using_socket(_SlowSocket())

    threads = [threading.Thread(target=lambda: socketutil.send_msg('q')) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert state['max_inflight'] == 1, (
        f"同一 socket 上出现 {state['max_inflight']} 个交叠的收包，/"
        f'overlap={state["overlap"]}；收发必须串行')
