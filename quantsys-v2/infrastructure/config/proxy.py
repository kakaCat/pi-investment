"""代理环境变量边界管理。

akshare 等三方库在请求时从 ``os.environ`` 读取 ``HTTP_PROXY`` / ``HTTPS_PROXY``，
无法靠 DI 注入。本模块是唯一的边界：在调用点临时写/清这些变量，并恢复原状。

配置真相源在 ``ProxySettings``（``infrastructure/config/settings.py``），
本模块不自行读取环境变量。
"""
import os
from contextlib import contextmanager
from typing import Optional

from infrastructure.config.settings import ProxySettings

# akshare 读取的大小写键名（与历史 patch.dict 一致）
_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")


@contextmanager
def proxy_disabled():
    """临时清空代理环境变量（置为空字符串），退出时恢复原状。

    等价于 akshare adapters 历史上的
    ``patch.dict(os.environ, {'HTTP_PROXY': '', ...}, clear=False)``。
    """
    saved = {k: os.environ.get(k) for k in _PROXY_KEYS}
    try:
        for k in _PROXY_KEYS:
            os.environ[k] = ""
        yield
    finally:
        for k in _PROXY_KEYS:
            original = saved[k]
            if original is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = original


@contextmanager
def apply_proxy(proxy: Optional[ProxySettings] = None):
    """按已解析的 ProxySettings 写入代理环境变量，退出时恢复原状。

    若 proxy 为空（未配置）则等同于 proxy_disabled()。
    """
    if proxy is None:
        with proxy_disabled():
            yield
        return

    saved = {k: os.environ.get(k) for k in _PROXY_KEYS}
    env_overlay = {}
    if proxy.http_proxy:
        env_overlay["HTTP_PROXY"] = env_overlay["http_proxy"] = proxy.http_proxy
    if proxy.https_proxy:
        env_overlay["HTTPS_PROXY"] = env_overlay["https_proxy"] = proxy.https_proxy
    if proxy.all_proxy:
        env_overlay["ALL_PROXY"] = env_overlay["all_proxy"] = proxy.all_proxy

    try:
        os.environ.update(env_overlay)
        yield
    finally:
        for k in _PROXY_KEYS:
            original = saved[k]
            if original is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = original
