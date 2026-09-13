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


def _close_baostock_socket():
    """关闭 baostock 当前会话 socket（看门狗触发，使阻塞中的 connect/recv 抛错）"""
    try:
        import baostock.common.context as bs_context
        sock = getattr(bs_context, 'default_socket', None)
        if sock is not None:
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
