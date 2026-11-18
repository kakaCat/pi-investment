from qs_notification.infrastructure.formatters.opportunity_scan_formatter import (
    render_opportunity_scan_summary,
)


def opportunity(symbol="600519.SH", name="贵州茅台", score=92, **overrides):
    value = {
        "symbol": symbol,
        "name": name,
        "score": score,
        "technical_score": 90,
        "fundamental_score": 88,
        "capital_score": 86,
        "risk_level": "medium",
        "reasons": ["技术面突破", "资金持续流入", "第三条不展示"],
    }
    value.update(overrides)
    return value


def test_renders_scores_reasons_and_rule_status():
    title, body = render_opportunity_scan_summary(
        [opportunity(), opportunity("000001.SZ", "平安银行", 85)],
        [
            {"symbol": "600519.SH", "action": "created", "rule_id": 123},
            {"symbol": "000001.SZ", "action": "skipped", "reason": "已存在1条启用规则"},
        ],
        scanned=356,
        scored=350,
        trade_date="2026-10-27",
    )

    assert title == "【每日机会扫描】2026-10-27｜2 个高分机会"
    assert "扫描 356 只｜评分成功 350 只｜≥80 分 2 个" in body
    assert "贵州茅台（600519.SH）｜92 分｜中风险" in body
    assert "技术 90｜基本面 88｜资金 86" in body
    assert "依据：技术面突破；资金持续流入" in body
    assert "第三条不展示" not in body
    assert "已建规则 #123" in body
    assert "未重复创建：已存在1条启用规则" in body
    assert "不自动交易" in body


def test_read_only_and_missing_reasons_are_explicit():
    _, body = render_opportunity_scan_summary(
        [opportunity(reasons=[], reason="")], [],
        scanned=1, scored=1, trade_date="2026-10-27",
        auto_create_rules=False,
    )

    assert "依据：暂无评分依据" in body
    assert "盯盘：只读扫描，未建规则" in body


def test_only_high_scores_and_first_ten_are_rendered():
    opportunities = [opportunity(f"{index:06d}.SZ", f"股票{index}", 80 + index)
                     for index in range(12)]
    opportunities.append(opportunity("700000.SZ", "低分股票", 79))

    title, body = render_opportunity_scan_summary(
        opportunities, [], scanned=13, scored=13, trade_date="2026-10-27")

    assert "12 个高分机会" in title
    assert "低分股票" not in body
    assert "另有 2 个高分机会未展开" in body


def test_failed_rule_status_is_visible():
    _, body = render_opportunity_scan_summary(
        [opportunity()],
        [{"symbol": "600519.SH", "action": "failed", "reason": "数据库不可用"}],
        scanned=1, scored=1, trade_date="2026-10-27",
    )

    assert "盯盘：创建失败：数据库不可用" in body
