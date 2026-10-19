"""S11-A 兼容 shim：application.services.base_service 已迁入
qs_kernel.application.services.base_service。

迁移见方案卡 docs/plans/package-boundaries-import-linter.md（§S11）。
30 天观察期后删除。
"""
from qs_kernel.application.services.base_service import *  # noqa: F401,F403
