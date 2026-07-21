import json
from pathlib import Path

from application.services.benchmark_service import BenchmarkService


def _write_fake_benchmark(path: Path, output_name: str):
    path.write_text(
        "\n".join(
            [
                "import json",
                "from pathlib import Path",
                "out = Path(__file__).parent / 'results' / %r" % output_name,
                "out.parent.mkdir(parents=True, exist_ok=True)",
                "out.write_text(json.dumps({'scenarios': [{'name': 'tiny', 'speedup': 2.0}]}))",
                "print('fake benchmark complete')",
            ]
        ),
        encoding="utf-8",
    )


def test_lists_known_benchmarks(tmp_path):
    service = BenchmarkService(project_root=tmp_path)

    benchmarks = service.list_benchmarks()

    assert any(item["id"] == "factors" for item in benchmarks)
    assert any(item["script"] == "benchmark_cache.py" for item in benchmarks)


def test_runs_selected_benchmark_and_writes_artifacts(tmp_path):
    benchmarks_dir = tmp_path / "benchmarks"
    benchmarks_dir.mkdir()
    _write_fake_benchmark(benchmarks_dir / "benchmark_factors.py", "benchmark_factors.json")

    service = BenchmarkService(project_root=tmp_path)

    result = service.run_benchmarks(["factors"], timeout_seconds=10)

    assert result["action"] == "benchmark_run"
    assert result["status"] == "success"
    assert result["requested"] == ["factors"]
    assert result["runs"][0]["id"] == "factors"
    assert result["runs"][0]["status"] == "success"
    assert result["runs"][0]["stdout"]
    assert Path(result["report_path"]).exists()

    raw_results = json.loads((benchmarks_dir / "results" / "all_results.json").read_text())
    assert raw_results["benchmark_results"]["benchmark_factors"]["scenarios"][0]["speedup"] == 2.0


def test_rejects_unknown_benchmark(tmp_path):
    service = BenchmarkService(project_root=tmp_path)

    try:
        service.run_benchmarks(["unknown"])
    except ValueError as exc:
        assert "Unknown benchmark" in str(exc)
    else:
        raise AssertionError("Expected unknown benchmark to be rejected")


def test_runs_database_benchmark_without_legacy_script(tmp_path):
    service = BenchmarkService(project_root=tmp_path)

    result = service.run_benchmarks(["database"], timeout_seconds=10)

    assert result["status"] == "success"
    assert result["requested"] == ["database"]
    assert result["runs"][0]["id"] == "database"
    assert result["runs"][0]["script"] == "service:database"
    assert result["runs"][0]["status"] == "success"

    raw_results = json.loads((tmp_path / "benchmarks" / "results" / "all_results.json").read_text())
    db_results = raw_results["benchmark_results"]["benchmark_database"]
    assert db_results["test_name"] == "database_queries"
    assert db_results["source"] == "BenchmarkService"
    assert db_results["scenarios"]
