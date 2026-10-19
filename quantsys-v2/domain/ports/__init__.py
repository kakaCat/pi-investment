"""S11-A 兼容 shim：domain.ports 已迁入 qs_kernel.domain.ports。

迁移见方案卡 docs/plans/package-boundaries-import-linter.md（§S11）。
30 天观察期后删除；期间旧路径 import 经此桥接（注意：旧长名与 kernel 名
会双实例化同一源文件，位置参数语义依赖全局单例处需留意）。
"""
import qs_kernel.domain.ports as _kernel_mod
from qs_kernel.domain.ports import *  # noqa: F401,F403

__path__ = list(__path__) + list(_kernel_mod.__path__)
