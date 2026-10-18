"""已迁移占位 shim：quantlib 已抽离为独立二方包 `qs-quantlib`（packages/qs_quantlib）。

保留本兼容层用于吸收未跟踪代码/实验脚本中的旧路径 import。
新代码一律使用 `from qs_quantlib import ...`；本 shim 计划在 30 天观察期后删除。
"""
import warnings as _warnings

try:
    import qs_quantlib as _pkg
    from qs_quantlib import *  # noqa: F401,F403
    __path__ = _pkg.__path__
except ImportError as _e:  # pragma: no cover
    _warnings.warn(f"旧路径 domain.quantlib 已迁移为 qs_quantlib，但包不可导入: {_e}")
