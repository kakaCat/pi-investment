"""infrastructure.config 兼容 shim（S11 · Slice A · 包边界工程）。

原生实现已迁至 packages/qs_kernel（qs_kernel.infrastructure.config）。本文件仅保留过渡 shim：
- ``import infrastructure.config`` 及 ``from infrastructure.config.X import ...`` 旧路径仍可用（30 天观察期，迁移卡：docs/plans/package-boundaries-import-linter.md §11）。
- ``__path__`` 追加原生实现目录；旧路径.resolve 子模块到 kernel 原文件；本目录在 L1 本地保留 cache_factory.py（零调用方、依赖 infrastructure.cache）与 data_pipeline.yaml（服务 cwd 相对路径、生产未接线）。
- 与 datasources 先例不同，这里采用「追加路径 + 星号转发」而非 ``__path__ = 原生.__path__`` 覆盖式，避免 L1 本地文件因 __path__ 丢失而丢失（cache_factory 若有调用方也可活）。
观察期完成后删除本 shim 并移除对应观察项。
"""
import qs_kernel.infrastructure.config as _kernel_config
from qs_kernel.infrastructure.config import *  # noqa: F401,F403

__path__ = list(__path__) + list(_kernel_config.__path__)  # noqa: F811
from qs_kernel.infrastructure.config import get_redis_config  # noqa: F401,E402
# cache_factory 本体留 L1（依赖适配层 infrastructure.cache，kernel 不收编）；旧路径消费方经此处显式转发
from infrastructure.config.cache_factory import (  # noqa: F401,E402
    create_cache_service,
    create_redis_client,
)
