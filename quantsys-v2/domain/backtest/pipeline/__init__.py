"""Pipeline support components (domain layer).

历史说明: 本包曾 re-export infrastructure.pipeline 的 PipelineErrorHandler /
DataPipelineMonitor 等组件,构成 domain→infrastructure 反向依赖。2026-08-05
核查全仓无任何模块通过 domain.quantlib.pipeline 引用这些 re-export
(tests/deprecated/ 直接 import infrastructure.pipeline,不经此包),
故移除该兼容 shim。

domain 本地的 DataPipelineMonitor 见 domain.quantlib.pipeline.monitor
(event_bus 由外层注入,不依赖 infrastructure)。
"""
