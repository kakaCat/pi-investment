"""出站网络偏好（2026-09-13，w-adb088f2）

背景（本机实测）：getaddrinfo 对多个行情域名**先返回 IPv6 地址**，而本机 IPv6 实际不可达
（OSError 51 Network is unreachable）。urllib3/requests 的 socket.create_connection 按
getaddrinfo 顺序逐个尝试，每个 IPv6 地址都要等一次 SYN 超时（约 2s）才回退 IPv4：

    qt.gtimg.cn 有 4 个 AAAA 记录 → 首次连接固定多付 ~8.07s 才落到 IPv4（IPv4 直连 0.05s）
    对照：curl 只需 0.32s（curl 实现了 Happy Eyeballs，IPv4/IPv6 并行尝试）

后果不只是慢：每只股票各新建一次连接、各付一次 8s（2 只持仓的账户查询 = 16.4s，
超过 agent 工具 10s 超时）。历史上这些症状被误读成"这些数据源不稳定/超时"，导致
provider 顺序被反复调整（见 manager.quote_providers 注释与 sina/akshare 的降级说明）。

处理：进程级把 urllib3 的地址族收敛到 IPv4（urllib3 官方开关 allowed_gai_family）。
环境变量 QUANTSYS_FORCE_IPV4=0 可关闭，便于排查真实 IPv6 问题。
"""
import os
import socket

_APPLIED = False


def _ipv4_only():
    """urllib3 会用它决定 create_connection 的地址族"""
    return socket.AF_INET


def prefer_ipv4() -> bool:
    """把 urllib3 出站连接的地址族收敛到 IPv4。幂等：重复调用无副作用。

    Returns:
        True=本进程已启用 IPv4 优先；False=按环境变量显式关闭
    """
    global _APPLIED
    if os.environ.get("QUANTSYS_FORCE_IPV4", "1") == "0":
        return False
    try:
        import urllib3.util.connection as urllib3_cn
    except Exception:
        return False
    if urllib3_cn.allowed_gai_family is not _ipv4_only:
        urllib3_cn.allowed_gai_family = _ipv4_only
        try:
            import structlog
            structlog.get_logger(__name__).info(
                "出站连接已收敛到 IPv4（规避本机 IPv6 黑洞导致的每连接 ~8s 超时）"
            )
        except Exception:
            pass
    _APPLIED = True
    return True


def is_ipv4_preferred() -> bool:
    """供健康检查/测试断言当前进程的地址族偏好"""
    try:
        import urllib3.util.connection as urllib3_cn
        return urllib3_cn.allowed_gai_family is _ipv4_only
    except Exception:
        return False
