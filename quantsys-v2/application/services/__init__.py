# QuantSys V2 Services
#
# 不在此做 `from . import order_service` 等急切导入（2026-08-20 segfault 修复）：
# order_service → data_service → 数据源层会拉起 polars/torch 等重依赖，
# 导致任何 `application.services.*` 的轻量使用者（如 ML 训练）都被动加载
# 多份 OpenMP 运行时，fit 时段错误。调用方一律显式
# `from application.services import order_service`（Python 会自行解析子模块）。
