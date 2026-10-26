"""qs_plan 应用层：plan_service（生命周期）、plan_compiler（幂等编译）、
plan_aggregator（today 视图）、reflection_pack_service（反思材料包）。

本层编排端口与兄弟包，不直连外部数据源；仓储走 L1
``adapters/outbound/repositories/trading_plan_repository.py``（与 watch 系同口径）。
"""
