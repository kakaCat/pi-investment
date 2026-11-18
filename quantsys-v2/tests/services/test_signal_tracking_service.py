from qs_sourcing.application.services.signal_tracking_service import SignalTrackingService


def test_mature_count_only_counts_signals_with_5d_performance():
    service = SignalTrackingService()
    signals = [
        {
            "grade": "A",
            "source": "opportunity_scan",
            "hit_5d": True,
            "return_5d": 0.08,
            "hit_10d": None,
            "return_10d": None,
            "hit_20d": None,
            "return_20d": None,
        },
        {
            "grade": "A",
            "source": "watch_rule",
            "hit_5d": None,
            "return_5d": None,
            "hit_10d": None,
            "return_10d": None,
            "hit_20d": None,
            "return_20d": None,
        },
    ]

    by_grade = service._calculate_grade_stats(signals)
    by_source = service._calculate_source_stats(signals)

    assert by_grade["A"]["count"] == 2
    assert by_grade["A"]["mature_count"] == 1
    assert by_grade["A"]["hit_rate_5d"] == 1.0
    assert by_grade["A"]["avg_return_5d"] == 0.08
    assert by_source["opportunity_scan"]["count"] == 1
    assert by_source["opportunity_scan"]["mature_count"] == 1
    assert by_source["watch_rule"]["count"] == 1
    assert by_source["watch_rule"]["mature_count"] == 0
    assert by_source["watch_rule"]["hit_rate_5d"] is None


def test_empty_grade_has_zero_mature_count():
    service = SignalTrackingService()
    stats = service._calculate_grade_stats([])
    assert stats["A"]["count"] == 0
    assert stats["A"]["mature_count"] == 0
