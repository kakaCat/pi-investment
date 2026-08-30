#!/usr/bin/env python3
"""
综合性能基准测试运行器

基准测试统一通过 BenchmarkService 执行；数据库查询 benchmark 已内置到服务中，
不再依赖独立的 benchmark_database.py 或 database/ 目录。

Architecture:
- Domain layer (this file) defines the benchmark runner
- Application layer provides BenchmarkService implementation
- Infrastructure layer wires them together
"""

import json
import sys
from pathlib import Path
from typing import Optional, Any


def main(benchmark_service: Optional[Any] = None) -> int:
    """
    Run all benchmarks.

    Args:
        benchmark_service: BenchmarkService instance (injected by infrastructure layer)
                          If None, attempts to create one (fallback for backward compatibility)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if benchmark_service is None:
        # Fallback: create service directly (for backward compatibility)
        # TODO: Make injection mandatory after all callers are updated
        try:
            from application.services.benchmark_service import BenchmarkService
            benchmark_service = BenchmarkService()
            print("Warning: BenchmarkService not injected, using fallback (should be injected)")
        except ImportError as e:
            print(f"Error: Cannot import BenchmarkService: {e}")
            print("Please provide benchmark_service via dependency injection")
            return 1

    result = benchmark_service.run_benchmarks(timeout_seconds=600)

    print("=" * 80)
    print("Quantsys-v2 综合性能基准测试")
    print("=" * 80)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n报告已保存到: {result['report_path']}")
    print(f"原始数据已保存到: {result['results_path']}")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
