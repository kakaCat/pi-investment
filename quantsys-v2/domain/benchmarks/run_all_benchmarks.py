#!/usr/bin/env python3
"""
综合性能基准测试运行器

基准测试统一通过 BenchmarkService 执行；数据库查询 benchmark 已内置到服务中，
不再依赖独立的 benchmark_database.py 或 database/ 目录。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from application.services.benchmark_service import BenchmarkService


def main() -> int:
    service = BenchmarkService()
    result = service.run_benchmarks(timeout_seconds=600)

    print("=" * 80)
    print("Quantsys-v2 综合性能基准测试")
    print("=" * 80)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n报告已保存到: {result['report_path']}")
    print(f"原始数据已保存到: {result['results_path']}")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
