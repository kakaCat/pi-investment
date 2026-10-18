"""
Quantlib Infrastructure Components
====================================

**角色定位**: 基础设施层的 quantlib 核心组件（配置、验证器、投资组合计算器）。

**模块结构**:
    - core: 核心配置、验证器、投资组合计算器

（数据适配器已归 apps：adapters.outbound.datasources.providers.quantlib，2026-10-19 shim 移除）

**重要**: 为避免循环依赖，不在此 __init__ 中自动导入子模块。
         使用时请显式从子模块导入：

Usage:
    ```python
    # 正确 - 显式从子模块导入
    from infrastructure.quantlib.core.portfolio_calculator import PortfolioCalculator

    # 错误 - 会触发循环依赖
    from infrastructure.quantlib import get_adapter  # ❌ 不要这样做
    ```

Architecture Notes:
    这些组件原本在 domain/quantlib，已于 Phase 1 下沉到 infrastructure 层。
    （原 adapters/ 向后兼容 shim 已于 2026-10-19 移除——自述 remove-after 2026-09-19 过期，消费 7 站全量改线 canonical。）

Circular Dependency Prevention:
    adapters.outbound.datasources.providers.quantlib.factor_calculator_adapter
    → domain.factors.library.moving_average
    → domain.factors.library.base
    → infrastructure.quantlib.core.base_calculator

    若在此 __init__.py 中自动导入子模块，会形成循环。
    解决方案：不在 __init__ 中导入，由用户显式导入子模块。

Refactoring History:
    - 2026-08-23: Phase 1 - 从 qs_quantlib 下沉到 infrastructure.quantlib
    - 2026-08-23: Phase 4 - 移除 __init__ 中的导入以打破循环依赖
    - 2026-10-19: adapters 向后兼容 shim 移除（消费 7 站改线 canonical 导入）
"""

# 不导入任何子模块，避免循环依赖
# 用户需显式从 .core 导入

__all__ = []
