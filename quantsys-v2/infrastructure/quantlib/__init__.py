"""
Quantlib Infrastructure Components
====================================

**角色定位**: 基础设施层的 quantlib 组件，提供数据适配器和核心工具。

**模块结构**:
    - adapters: 数据适配器和因子计算适配器（向后兼容 shim）
    - core: 核心配置、验证器、投资组合计算器

**重要**: 为避免循环依赖，不在此 __init__ 中自动导入子模块。
         使用时请显式从子模块导入：

Usage:
    ```python
    # 正确 - 显式从子模块导入
    from infrastructure.quantlib.adapters import get_adapter, get_factor_adapter
    from infrastructure.quantlib.core.portfolio_calculator import PortfolioCalculator

    # 错误 - 会触发循环依赖
    from infrastructure.quantlib import get_adapter  # ❌ 不要这样做
    ```

Architecture Notes:
    这些组件原本在 domain/quantlib，已于 Phase 1 下沉到 infrastructure 层。
    adapters/ 目录是向后兼容 shim，实际实现在 adapters.outbound.datasources.providers.quantlib。

Circular Dependency Prevention:
    infrastructure.quantlib.adapters (shim)
    → adapters.outbound.datasources.providers.quantlib.factor_calculator_adapter
    → domain.factors.library.moving_average
    → domain.factors.library.base
    → infrastructure.quantlib.core.base_calculator

    如果在此 __init__.py 中 `from .adapters import *`，会形成循环。
    解决方案：不在 __init__ 中导入，由用户显式导入子模块。

Refactoring History:
    - 2026-08-23: Phase 1 - 从 domain.quantlib 下沉到 infrastructure.quantlib
    - 2026-08-23: Phase 4 - 移除 __init__ 中的导入以打破循环依赖
"""

# 不导入任何子模块，避免循环依赖
# 用户需显式从 .adapters 或 .core 导入

__all__ = []
