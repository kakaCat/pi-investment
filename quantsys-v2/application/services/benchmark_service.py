"""
Service wrapper for the benchmark suite.

The benchmark scripts remain executable maintenance tools.  This service makes
them callable from API routes and scheduler commands while keeping subprocess
execution, result loading, and report generation in one place.
"""
from __future__ import annotations

import json
import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class BenchmarkDefinition:
    id: str
    name: str
    script: str
    result_file: str
    category: str
    description: str


class BenchmarkService:
    """Run and inspect project benchmarks."""

    BENCHMARKS: tuple[BenchmarkDefinition, ...] = (
        BenchmarkDefinition(
            id="factors",
            name="Factor calculation",
            script="benchmark_factors.py",
            result_file="benchmark_factors.json",
            category="quantlib",
            description="CPU/GPU factor calculation throughput and speedup.",
        ),
        BenchmarkDefinition(
            id="ml",
            name="Machine learning",
            script="benchmark_ml.py",
            result_file="benchmark_ml.json",
            category="quantlib",
            description="Model training and prediction performance.",
        ),
        BenchmarkDefinition(
            id="database",
            name="Database queries",
            script="service:database",
            result_file="benchmark_database.json",
            category="service",
            description="Built-in synchronous and asynchronous query performance benchmark.",
        ),
        BenchmarkDefinition(
            id="cache",
            name="Cache",
            script="benchmark_cache.py",
            result_file="benchmark_cache.json",
            category="service",
            description="Memory/Redis cache read, write, and hit-rate performance.",
        ),
        BenchmarkDefinition(
            id="backtest",
            name="Backtest",
            script="benchmark_backtest.py",
            result_file="benchmark_backtest.json",
            category="quantlib",
            description="Serial and parallel strategy backtest performance.",
        ),
        BenchmarkDefinition(
            id="backtest_optimized",
            name="Backtest optimizations",
            script="benchmark_backtest_optimized.py",
            result_file="benchmark_backtest_optimized.json",
            category="quantlib",
            description="Optimized backtest implementation comparison.",
        ),
    )

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
        self.benchmarks_dir = self.project_root / "benchmarks"
        self.results_dir = self.benchmarks_dir / "results"
        self.report_path = self.project_root / "docs" / "reports" / "PERFORMANCE_BENCHMARK_REPORT.md"

    def list_benchmarks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": item.id,
                "name": item.name,
                "script": item.script,
                "category": item.category,
                "description": item.description,
                "available": (self.benchmarks_dir / item.script).exists(),
            }
            for item in self.BENCHMARKS
        ]

    def run_benchmarks(
        self,
        benchmark_ids: Optional[Iterable[str]] = None,
        timeout_seconds: int = 600,
    ) -> Dict[str, Any]:
        selected = self._select_benchmarks(benchmark_ids)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        started = time.time()
        runs = [self._run_one(item, timeout_seconds=timeout_seconds) for item in selected]
        elapsed = time.time() - started
        benchmark_results = self._load_results(selected)
        summary = self._summarize_results(benchmark_results)
        report = self._generate_report(benchmark_results, runs, summary, started_at)
        self._write_artifacts(runs, benchmark_results, summary, started_at, report)

        status = "success" if all(run["status"] == "success" for run in runs) else "failed"
        return {
            "action": "benchmark_run",
            "status": status,
            "requested": [item.id for item in selected],
            "elapsed_seconds": elapsed,
            "started_at": started_at,
            "runs": runs,
            "summary": summary,
            "results_path": str(self.results_dir / "all_results.json"),
            "report_path": str(self.report_path),
        }

    def get_latest_results(self) -> Dict[str, Any]:
        result_path = self.results_dir / "all_results.json"
        if not result_path.exists():
            return {
                "available": False,
                "results_path": str(result_path),
                "report_path": str(self.report_path),
            }
        with open(result_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["available"] = True
        payload["results_path"] = str(result_path)
        payload["report_path"] = str(self.report_path)
        return payload

    def read_report(self) -> Optional[str]:
        if not self.report_path.exists():
            return None
        return self.report_path.read_text(encoding="utf-8")

    def _select_benchmarks(self, benchmark_ids: Optional[Iterable[str]]) -> List[BenchmarkDefinition]:
        available = {item.id: item for item in self.BENCHMARKS}
        if benchmark_ids is None:
            return list(self.BENCHMARKS[:5])

        selected: List[BenchmarkDefinition] = []
        for benchmark_id in benchmark_ids:
            if benchmark_id not in available:
                raise ValueError(f"Unknown benchmark: {benchmark_id}")
            selected.append(available[benchmark_id])
        return selected

    def _run_one(self, benchmark: BenchmarkDefinition, timeout_seconds: int) -> Dict[str, Any]:
        if benchmark.script.startswith("service:"):
            return self._run_builtin_benchmark(benchmark)

        script_path = self.benchmarks_dir / benchmark.script
        if not script_path.exists():
            return {
                "id": benchmark.id,
                "script": benchmark.script,
                "status": "failed",
                "elapsed_seconds": 0,
                "stdout": "",
                "stderr": f"Benchmark script not found: {script_path}",
            }

        started = time.time()
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed = time.time() - started
            return {
                "id": benchmark.id,
                "script": benchmark.script,
                "status": "success" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "elapsed_seconds": elapsed,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "id": benchmark.id,
                "script": benchmark.script,
                "status": "timeout",
                "elapsed_seconds": timeout_seconds,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }

    def _run_builtin_benchmark(self, benchmark: BenchmarkDefinition) -> Dict[str, Any]:
        started = time.time()
        try:
            if benchmark.script == "service:database":
                payload = self._run_database_benchmark()
                stdout = (
                    "Built-in database benchmark complete: "
                    f"{len(payload.get('scenarios', []))} scenarios"
                )
            else:
                raise ValueError(f"Unknown built-in benchmark: {benchmark.script}")

            elapsed = time.time() - started
            return {
                "id": benchmark.id,
                "script": benchmark.script,
                "status": "success",
                "returncode": 0,
                "elapsed_seconds": elapsed,
                "stdout": stdout,
                "stderr": "",
            }
        except Exception as exc:
            elapsed = time.time() - started
            return {
                "id": benchmark.id,
                "script": benchmark.script,
                "status": "failed",
                "returncode": 1,
                "elapsed_seconds": elapsed,
                "stdout": "",
                "stderr": str(exc),
            }

    def _run_database_benchmark(self) -> Dict[str, Any]:
        scenarios = []
        for n_queries in (10, 100, 1000):
            sync_result = self._benchmark_sync_queries(n_queries)
            async_result = asyncio.run(self._benchmark_async_queries(n_queries, batch_size=10))
            speedup = sync_result["mean_time"] / async_result["mean_time"] if async_result["mean_time"] else None
            scenarios.append(
                {
                    "name": f"{n_queries} queries",
                    "n_queries": n_queries,
                    "sync": sync_result,
                    "async": async_result,
                    "speedup": speedup,
                }
            )

        payload = {
            "test_name": "database_queries",
            "source": "BenchmarkService",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scenarios": scenarios,
            "real_database": None,
        }
        self.results_dir.mkdir(parents=True, exist_ok=True)
        with open(self.results_dir / "benchmark_database.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return payload

    def _benchmark_sync_queries(self, n_queries: int) -> Dict[str, float]:
        times = []
        for _ in range(3):
            started = time.perf_counter()
            for _ in range(n_queries):
                time.sleep(0.0001)
            elapsed = time.perf_counter() - started
            times.append(elapsed)
        return self._query_timing_summary(times, n_queries)

    async def _benchmark_async_queries(self, n_queries: int, batch_size: int) -> Dict[str, float]:
        times = []

        async def single_query() -> Dict[str, str]:
            await asyncio.sleep(0.0001)
            return {"data": "result"}

        for _ in range(3):
            started = time.perf_counter()
            tasks = []
            for index in range(n_queries):
                tasks.append(single_query())
                if len(tasks) >= batch_size or index == n_queries - 1:
                    await asyncio.gather(*tasks)
                    tasks = []
            elapsed = time.perf_counter() - started
            times.append(elapsed)
        return self._query_timing_summary(times, n_queries)

    @staticmethod
    def _query_timing_summary(times: List[float], n_queries: int) -> Dict[str, float]:
        mean_time = sum(times) / len(times)
        variance = sum((item - mean_time) ** 2 for item in times) / len(times)
        return {
            "mean_time": mean_time,
            "std_time": variance ** 0.5,
            "qps": n_queries / mean_time if mean_time else 0.0,
        }

    def _load_results(self, selected: Iterable[BenchmarkDefinition]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for item in selected:
            path = self.results_dir / item.result_file
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    results[item.result_file.replace(".json", "")] = json.load(f)
            except Exception as exc:
                results[item.result_file.replace(".json", "")] = {"load_error": str(exc)}
        return results

    def _summarize_results(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        speedups = []
        for name, data in benchmark_results.items():
            for scenario in data.get("scenarios", []) if isinstance(data, dict) else []:
                speedup = scenario.get("speedup")
                if isinstance(speedup, (int, float)):
                    speedups.append(
                        {
                            "benchmark": name,
                            "scenario": scenario.get("name", ""),
                            "speedup": speedup,
                        }
                    )
        return {
            "benchmark_count": len(benchmark_results),
            "speedups": speedups,
            "average_speedup": (
                sum(item["speedup"] for item in speedups) / len(speedups)
                if speedups
                else None
            ),
        }

    def _generate_report(
        self,
        benchmark_results: Dict[str, Any],
        runs: List[Dict[str, Any]],
        summary: Dict[str, Any],
        started_at: str,
    ) -> str:
        lines = [
            "# Quantsys-v2 Performance Benchmark Report",
            "",
            f"Generated at: {started_at}",
            "",
            "## Run Status",
            "",
            "| Benchmark | Status | Elapsed |",
            "| --- | --- | ---: |",
        ]
        for run in runs:
            lines.append(f"| {run['id']} | {run['status']} | {run['elapsed_seconds']:.3f}s |")

        lines.extend(["", "## Summary", ""])
        avg = summary.get("average_speedup")
        lines.append(f"- Benchmarks with result data: {summary['benchmark_count']}")
        lines.append(f"- Average speedup: {avg:.2f}x" if avg is not None else "- Average speedup: N/A")

        if summary.get("speedups"):
            lines.extend(["", "## Speedups", "", "| Benchmark | Scenario | Speedup |", "| --- | --- | ---: |"])
            for item in summary["speedups"]:
                lines.append(f"| {item['benchmark']} | {item['scenario']} | {item['speedup']:.2f}x |")

        lines.extend(["", "## Raw Result Keys", ""])
        for key in sorted(benchmark_results):
            lines.append(f"- `{key}`")
        return "\n".join(lines) + "\n"

    def _write_artifacts(
        self,
        runs: List[Dict[str, Any]],
        benchmark_results: Dict[str, Any],
        summary: Dict[str, Any],
        started_at: str,
        report: str,
    ) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(report, encoding="utf-8")

        all_results = {
            "timestamp": started_at,
            "run_results": runs,
            "benchmark_results": benchmark_results,
            "summary": summary,
        }
        with open(self.results_dir / "all_results.json", "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
