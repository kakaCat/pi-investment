"""
BaseORMRepository._get_cursor() 兼容垫片测试。

背景：data_quality_check 假成功根因——data_gap_detector / data_validator
等遗留服务仍调用旧 BaseRepository 的 `_get_cursor()` 原生 SQL 接口，
但注入的 kline_repo 已换成 ORM 版（无此方法），抛
"'KlineORMRepository' object has no attribute '_get_cursor'"，
被上层吞掉后表现为"检查 0 只股票、质量评分 100"（2026-07-17 起）。
"""


def test_orm_repository_provides_legacy_cursor():
    """ORM Repository 必须提供旧式 _get_cursor()（RealDictCursor）"""
    from adapters.outbound.repositories.kline_repository import KlineORMRepository

    repo = KlineORMRepository()
    cursor = repo._get_cursor()
    try:
        cursor.execute("SELECT 1 AS one")
        row = cursor.fetchone()
        assert row['one'] == 1  # RealDictCursor：行以 dict 返回
    finally:
        cursor.close()


def test_orm_repository_cursor_recovers_after_reconnect():
    """连接被关闭后再次获取 cursor 应自动重建（lazy + pre_ping）"""
    from adapters.outbound.repositories.kline_repository import KlineORMRepository

    repo = KlineORMRepository()
    cursor = repo._get_cursor()
    cursor.close()
    # 模拟连接失效后重建
    if getattr(repo, '_raw_conn', None) is not None:
        repo._raw_conn.close()
    cursor2 = repo._get_cursor()
    try:
        cursor2.execute("SELECT 2 AS two")
        assert cursor2.fetchone()['two'] == 2
    finally:
        cursor2.close()
