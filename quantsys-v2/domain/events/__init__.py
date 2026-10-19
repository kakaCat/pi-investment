"""S11-A 兼容 shim：domain.events 已迁入 qs_kernel.domain.events。

迁移见方案卡 docs/plans/package-boundaries-import-linter.md（§S11）。
30 天观察期后删除。
"""
import qs_kernel.domain.events as _kernel_mod
from qs_kernel.domain.events import *  # noqa: F401,F403

__path__ = list(__path__) + list(_kernel_mod.__path__)
