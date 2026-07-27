"""策略发现结果共享存储（框架无关）— 从 adapters/inbound/api/routes/discovery.py 解耦而来

Flask 与 FastAPI 两个 API 层共享同一内存结果存储（重启丢失）。
"""

# 简易内存存储（重启丢失，后续可迁到 DB）
_results_store: dict = {}
