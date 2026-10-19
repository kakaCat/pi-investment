"""项目根目录定位（2026-10-19，包抽取路径漂移修复）。

背景：S 系列包抽取（qs_strategy/qs_ops 等）把文件物理位置下移了两层，
原先 `Path(__file__).parent.parent.parent` 的**固定深度**算法全部指错
（v13/v14 策略配置读取 2026-10-19 起全线失败即此根因）。

修法：不算深度，**向上找标记**——从调用文件出发逐级向上，找到含
marker 相对路径的目录即为项目根（quantsys-v2 目录）。
"""
from pathlib import Path
from typing import Union


def find_project_root(start: Union[str, Path, None] = None,
                      marker: str = 'live_trading/config_simulation.yaml') -> Path:
    """从 start（缺省=调用本函数没意义，请显式传 __file__）向上找项目根。

    Args:
        start: 起始文件/目录（各调用点传自己的 __file__）。
        marker: 项目根下一定存在的相对路径（缺省为 live_trading 主配置，
            策略配置目录场景可传 'live_trading/configs/strategies'）。

    Returns:
        含 marker 的目录（= quantsys-v2 项目根）。

    Raises:
        FileNotFoundError: 向上走到文件系统根仍未找到——响亮失败，
            绝不允许悄悄返回错误路径（错误路径 = 配置静默缺失的温床）。
    """
    p = Path(start).resolve() if start else Path.cwd()
    if p.is_file():
        p = p.parent
    for d in (p, *p.parents):
        if (d / marker).exists():
            return d
    raise FileNotFoundError(
        f'项目根定位失败：从 {p} 向上未找到 {marker}——'
        f'live_trading 配置目录缺失或被移动')
