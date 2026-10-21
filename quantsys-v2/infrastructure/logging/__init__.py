"""S11-A 兼容 shim：infrastructure.logging 已迁入 qs_kernel.infrastructure.logging。

迁移见方案卡 docs/plans/package-boundaries-import-linter.md（§S11）。
30 天观察期后删除。
"""
import qs_kernel.infrastructure.logging as _kernel_mod
from qs_kernel.infrastructure.logging import *  # noqa: F401,F403

__path__ = list(__path__) + list(_kernel_mod.__path__)
