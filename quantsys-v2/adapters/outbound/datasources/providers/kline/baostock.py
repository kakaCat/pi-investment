"""Baostock kline provider - 独立 TCP 服务体系（抗网页 WAF 封禁）

背景（2026-07-28）：eastmoney（akshare）与 tencent（ifzq.gtimg.cn）均封禁
本机 IP。baostock 是独立 TCP 长连接服务（非网页 API），体系不同，作为
K线网络源首选。

数据契约：volume 单位为股（无需归一）、amount 成交额（元）、turn 换手率（%）。
"""
import logging
import threading
import time
from typing import List, Optional
from datetime import datetime

from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

logger = logging.getLogger(__name__)

# baostock 库的 socket 没有超时（util/socketutil.py 裸 connect/recv），
# 对端黑洞（IP 被封但不 RST）时调用永久阻塞——2026-08-05 评分线程池挂死根因。
# 统一给每个 baostock 调用配看门狗：超时关闭底层 socket，阻塞调用立即抛错，
# provider 返回 None，DataProviderManager 正常降级到下一数据源。
_BAOSTOCK_CALL_TIMEOUT = 15  # 秒

# 2026-09-20：同一 socket 的「发送 → 收完一帧」必须串行。整个进程只有一个 baostock
# 会话（manager.py 只 new 一个 BaostockKlineProvider，context 里只有一个
# default_socket），而评分线程池与夜间回填会并发调用。交叠收发会让 A 线程读到 B 线程
# 的应答（实测 4 线程全部交叠），也正是「一个线程 logout 关 socket、另一个线程正在
# recv」→ 对端 FIN → 空转的触发路径。
_BAOSTOCK_SEND_LOCK = threading.RLock()

# 正在收包中的 socket 对象。看门狗据此关闭**本次调用实际持有的** socket——只关
# context.default_socket 不够：重新登录会把该全局引用换成新 socket，旧 socket 从此
# 无人能关，被孤立的调用只能永久阻塞（2026-09-20 三线程 24h 空转的生存机制）。
_BAOSTOCK_INFLIGHT = set()
_BAOSTOCK_INFLIGHT_LOCK = threading.Lock()

# 上游收包结束标记（baostock/util/socketutil.py 内联的同一字面量）
_BS_MSG_TAIL = b"<![CDATA[]]>\n"


def _register_inflight(sock):
    with _BAOSTOCK_INFLIGHT_LOCK:
        _BAOSTOCK_INFLIGHT.add(sock)


def _clear_inflight(sock):
    with _BAOSTOCK_INFLIGHT_LOCK:
        _BAOSTOCK_INFLIGHT.discard(sock)


def _close_baostock_socket():
    """关闭 baostock 会话 socket（看门狗触发，使阻塞中的 connect/recv 抛错）"""
    targets = []
    try:
        import baostock.common.context as bs_context
        cur = getattr(bs_context, 'default_socket', None)
        if cur is not None:
            targets.append(cur)
    except Exception:
        pass
    with _BAOSTOCK_INFLIGHT_LOCK:
        targets.extend(_BAOSTOCK_INFLIGHT)
    for sock in targets:
        try:
            sock.close()
        except Exception:
            pass


def _with_socket_timeout(fn, timeout: float = _BAOSTOCK_CALL_TIMEOUT):
    """在看门狗保护下执行 baostock 阻塞调用"""
    watchdog = threading.Timer(timeout, _close_baostock_socket)
    watchdog.daemon = True
    watchdog.start()
    try:
        return fn()
    finally:
        watchdog.cancel()


def _make_patched_send_msg():
    """构造 send_msg 的修正实现（与原实现的三处差异见下）"""
    import zlib

    import baostock.common.contants as cons
    import baostock.common.context as context

    def send_msg(msg):
        sock = getattr(context, 'default_socket', None) if hasattr(
            context, 'default_socket') else None
        if sock is None:
            print("you don't login.")
            return None
        try:
            with _BAOSTOCK_SEND_LOCK:
                sock.send(bytes(msg + "\n", encoding='utf-8'))
                receive = b""
                _register_inflight(sock)
                try:
                    while True:
                        recv = sock.recv(8192)
                        if not recv:
                            # 差异 1（本次修复核心）：对端 FIN 后 recv **立即返回 b""**、
                            # 永不阻塞，原实现拿 b"" 去比结束标记永远不成立 → while True
                            # 无限空转。实测 5001 三线程各 58% CPU、sys:user=3.29:1、
                            # socket 零流量，24h 烧掉约 1.75 核。
                            # 返回 None 与上游异常路径同形：调用方（history.py/loginout.py）
                            # 随即置 error_msg="网络接收错误。"，而该文案已在
                            # _SESSION_ERROR_MARKERS 里 → 既有重登逻辑接管。
                            print("baostock 连接已被对端关闭（recv 返回空），放弃本次收包")
                            return None
                        receive += recv
                        if receive[-len(_BS_MSG_TAIL):] == _BS_MSG_TAIL:
                            break
                finally:
                    # 差异 2：收包期间登记 socket，使看门狗能关掉**本次调用实际用的
                    # 那个对象**，而不是被重新登录换掉的全局引用。
                    _clear_inflight(sock)

            head_bytes = receive[0:cons.MESSAGE_HEADER_LENGTH]
            head_str = bytes.decode(head_bytes)
            head_arr = head_str.split(cons.MESSAGE_SPLIT)
            if head_arr[1] in cons.COMPRESSED_MESSAGE_TYPE_TUPLE:
                head_inner_length = int(head_arr[2])
                body_str = bytes.decode(zlib.decompress(
                    receive[cons.MESSAGE_HEADER_LENGTH:
                            cons.MESSAGE_HEADER_LENGTH + head_inner_length]))
                return head_str + body_str
            return bytes.decode(receive)
        except Exception as ex:
            print(ex)
            print("接收数据异常，请稍后再试。")
            return None

    return send_msg


def _patch_baostock_send_msg():
    """把修正版 send_msg 装回 baostock.util.socketutil（幂等）

    baostock 的调用点一律是 `import baostock.util.socketutil as sock` 后
    `sock.send_msg(...)`，替换模块属性即全局生效。pip 里的第三方代码不进仓库、
    不可改，只能在进程内打补丁。
    """
    try:
        import baostock.util.socketutil as socketutil
    except ImportError:
        return False  # 未安装 baostock 时 provider 本就降级，无需补丁
    if getattr(socketutil.send_msg, '_baostock_eof_fixed', False):
        return True
    patched = _make_patched_send_msg()
    patched._baostock_eof_fixed = True
    socketutil.send_msg = patched
    return True


_patch_baostock_send_msg()

# 日K 查询字段（baostock 文档）
_DAILY_FIELDS = 'date,code,open,high,low,close,volume,amount,turn'

# 会话级错误特征（长连接断开后的报错文案/异常），命中则重登重试一次。
# 永久错误（代码不支持、无数据）不在此列，绝不重试（2026-08-02 回填事故：
# 会话中断后几千只股票全部「网络接收错误」，provider 缓存会话从不重登）
_SESSION_ERROR_MARKERS = ('网络接收错误', '接收数据异常', 'Broken pipe', 'Connection aborted', 'RemoteDisconnected', 'Bad file descriptor')

# 登录可重试判定（2026-09-13，看板事件 79aaf17d）：会话类错误 + 超时/连接类。
# 与 _SESSION_ERROR_MARKERS 分开：后者决定「是否重置会话重登」，本组决定「登录是否值得重试」。
_LOGIN_RETRYABLE_MARKERS = _SESSION_ERROR_MARKERS + (
    'TimeoutError', 'timed out', 'timeout', 'Connection reset', 'Connection refused',
)


class BaostockKlineProvider(KlineProvider):
    """Kline provider using baostock TCP service (daily only)"""

    def __init__(self):
        # 最近一次失败的具体原因，供 DataProviderManager 聚合返回给调用方
        self.last_error: Optional[str] = None
        self._bs = None  # 已登录的 baostock 模块引用（进程内复用会话）

    @property
    def name(self) -> str:
        return "baostock"

    @staticmethod
    def _to_baostock_code(symbol: str) -> Optional[str]:
        """300750 -> sz.300750, 600519 -> sh.600519, 399006 -> sz.399006"""
        symbol = symbol.split('.')[0]  # 容忍 600519.SH 形式
        if symbol.startswith(('60', '68', '11', '51')):
            return f'sh.{symbol}'
        # '39' 为深市指数代码段（399001 深成指、399006 创业板指）
        if symbol.startswith(('00', '30', '12', '15', '39')):
            return f'sz.{symbol}'
        if symbol.startswith(('4', '8', '92')):
            return f'bj.{symbol}'
        return None

    _LOGIN_ATTEMPTS = 3
    _LOGIN_BACKOFF_SEC = (0.5, 1.5)

    def _ensure_login(self):
        """lazy 登录，进程内复用会话。返回 baostock 模块或 None

        2026-09-13（w-32314d00，看板事件 79aaf17d）：旧实现登录对上游瞬时抖动**零重试**
        —— baostock 返回 error_msg='网络接收错误。' 时直接 return None，调用方随即把该标的
        判为失败。实证：09-10 22:02 ~ 09-12 01:21（夜间批量回填窗口）累计 93 条同类日志、
        去重后 37 次事件。现对可重试类错误做有限重试：最多 3 次、退避 0.5s/1.5s；
        中间尝试打 WARNING、仅最终失败打 ERROR，避免一次上游抖动刷满错误台账。
        不可重试错误（服务端明确拒绝等）仍立即返回，不白等。
        """
        if self._bs is not None:
            return self._bs
        try:
            import baostock as bs
        except ImportError:
            self.last_error = "baostock 未安装（pip install baostock）"
            logger.error(self.last_error)
            return None

        last_msg = ""
        last_was_exc = False
        for attempt in range(self._LOGIN_ATTEMPTS):
            try:
                lg = _with_socket_timeout(bs.login)
                if lg.error_code == '0':
                    self._bs = bs
                    logger.info("baostock 登录成功")
                    return bs
                last_msg = str(getattr(lg, 'error_msg', '') or '登录失败（无 error_msg）')
                last_was_exc = False
            except Exception as e:  # noqa: BLE001 - 网络/超时类都要能被重试判定看到
                last_msg = f"{type(e).__name__}: {e}"
                last_was_exc = True

            retryable = any(m in last_msg for m in _LOGIN_RETRYABLE_MARKERS)
            if not retryable or attempt == self._LOGIN_ATTEMPTS - 1:
                break
            logger.warning(
                f"baostock 登录失败（第 {attempt + 1}/{self._LOGIN_ATTEMPTS} 次）：{last_msg}"
                f" —— 退避 {self._LOGIN_BACKOFF_SEC[attempt]}s 后重试")
            time.sleep(self._LOGIN_BACKOFF_SEC[attempt])

        prefix = "baostock 登录异常: " if last_was_exc else "baostock 登录失败: "
        self.last_error = f"{prefix}{last_msg}"
        logger.error(self.last_error)
        return None

    def _reset_session(self):
        """会话失效后重置（logout 旧会话并清空缓存），下次 _ensure_login 重新登录"""
        try:
            if self._bs is not None:
                self._bs.logout()
        except Exception:
            pass
        self._bs = None

    @staticmethod
    def _is_session_error(msg: str) -> bool:
        return any(m in msg for m in _SESSION_ERROR_MARKERS)

    @staticmethod
    def _normalize_date(value: str) -> str:
        """把日期归一为 baostock 要求的 YYYY-MM-DD（容忍 YYYYMMDD）。

        2026-09-13（w-32314d00，事件 d9361056）：data_backfiller 走
        start_date.replace("-", "") 传 **YYYYMMDD**，而 baostock 只认 ISO 格式——
        实测（本机复现，见 work-log）：
            YYYYMMDD -> query 返回 None（baostock 仅打印「日期格式不正确，请修改。」）
            ISO      -> error_code=0，正常返回数据
        返回 None 时旧代码直接取 rs.error_code → AttributeError: NoneType object has no
        attribute error_code，被当成「provider 失败」→ 3 分钟 150 条错误日志，
        且 baostock（抗网页 WAF 的独立 TCP 源）在这条链路里等于不可用。
        现在在 provider 边界做格式归一，调用方传哪种都行。
        """
        s = str(value or "").strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        return s


    def get_klines(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[KlineData]]:
        """Get daily kline data from baostock"""
        self.last_error = None

        if period != 'daily':
            self.last_error = f"仅支持 daily 周期，收到: {period}"
            logger.debug(f"Baostock provider only supports daily, got: {period}")
            return None

        code = self._to_baostock_code(symbol)
        if not code:
            self.last_error = f"代码 {symbol} 无法映射到交易所前缀"
            logger.warning(f"Cannot map symbol to baostock code: {symbol}")
            return None

        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)

        # 查询（会话级错误重登重试一次；永久错误/空数据不重试）
        rs = None
        for attempt in range(2):
            bs = self._ensure_login()
            if bs is None:
                return None
            try:
                rs = _with_socket_timeout(lambda: bs.query_history_k_data_plus(
                    code, _DAILY_FIELDS,
                    start_date=start_date, end_date=end_date,
                    frequency='d', adjustflag='2',  # 前复权，与 tencent qfq 对齐
                ))
            except Exception as e:
                if attempt == 0 and self._is_session_error(str(e)):
                    logger.warning(f"baostock 会话失效（{e}），重登后重试 {symbol}")
                    self._reset_session()
                    continue
                self.last_error = f"查询/解析异常: {type(e).__name__}: {e}"
                logger.error(f"Baostock kline provider failed for {symbol}: {e}")
                return None
            if rs is None:
                # baostock 在入参非法（如日期格式）时**直接返回 None** 而不给 error_code，
                # 旧代码在此 AttributeError（事件 d9361056 的 150 条日志来源）。
                # None 属永久错误：不重试，给出可读原因（格式归一后此分支基本不再走到）。
                self.last_error = (
                    f"baostock 未返回结果集（入参非法或无数据）: "
                    f"symbol={symbol}, {start_date}~{end_date}"
                )
                logger.warning(self.last_error)
                return None
            if rs.error_code != "0":
                if attempt == 0 and self._is_session_error(rs.error_msg):
                    logger.warning(f"baostock 会话失效（{rs.error_msg}），重登后重试 {symbol}")
                    self._reset_session()
                    continue
                self.last_error = f"baostock 查询失败: {rs.error_msg}"
                logger.warning(f"Baostock query error for {symbol}: {rs.error_msg}")
                return None
            break

        try:
            result = []
            prev_close = None
            while rs.next():
                row = rs.get_row_data()
                # 字段: date,code,open,high,low,close,volume(股),amount(元),turn(%)
                date_str = row[0]
                open_p, high, low, close = (
                    float(row[2]), float(row[3]), float(row[4]), float(row[5]))
                volume = int(float(row[6])) if row[6] else 0
                amount = float(row[7]) if row[7] else 0.0
                turn = float(row[8]) if row[8] else 0.0

                change_pct = (
                    round((close - prev_close) / prev_close * 100, 2)
                    if prev_close else 0.0
                )
                prev_close = close

                result.append(KlineData(
                    symbol=symbol,
                    date=date_str,
                    open=open_p,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    change_pct=change_pct,
                    amount=amount,
                    turnover_rate=turn,
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            if not result:
                self.last_error = f"baostock 无 {symbol} 的K线数据（代码不存在或该时段无交易）"
                logger.warning(f"Baostock returned no data for {symbol}")
                return None

            logger.info(f"Baostock provider returned {len(result)} klines for {symbol}")
            return result

        except Exception as e:
            self.last_error = f"查询/解析异常: {type(e).__name__}: {e}"
            logger.error(f"Baostock kline provider failed for {symbol}: {e}")
            return None
