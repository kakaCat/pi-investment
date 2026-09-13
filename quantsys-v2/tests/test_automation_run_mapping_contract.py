"""AutomationRun ORM 映射契约（2026-09-13，w-32314d00，REQ-24e15d t3）。

背景：本仓储曾把 metadata 列映射成不存在的 run_metadata（information_schema 实测库列为 metadata），
导致所有语句引用不存在的列 —— 在真实库上不可用（全模型 select 即 UndefinedColumn）。
本用例锁死「属性名 run_metadata ↔ 列名 metadata」这一契约，防止再次写错。
"""
from adapters.outbound.repositories.automation_repository import AutomationRun


def test_run_metadata_attribute_maps_to_real_db_column():
    # 注意取法：列 key 是 metadata（SQLAlchemy 以列名作 key），所以要用**属性**反射取映射，
    # 不能用 __table__.c.run_metadata（那不是 key）。
    prop = getattr(AutomationRun, 'run_metadata')
    cols = prop.property.columns
    assert len(cols) == 1
    assert cols[0].name == 'metadata', (
        'run_metadata 属性必须映射到真实库列 metadata（库里没有 run_metadata 这一列）'
    )


def test_table_columns_match_real_schema():
    names = {c.name for c in AutomationRun.__table__.columns}
    assert 'metadata' in names
    assert 'run_metadata' not in names, 'ORM 不得再引用不存在的 run_metadata 列'
    for expected in ('run_id', 'status', 'started_at', 'completed_at', 'execution_time_ms', 'error_message'):
        assert expected in names
