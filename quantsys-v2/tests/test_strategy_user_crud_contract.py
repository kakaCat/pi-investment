"""策略停用/更新/删除的仓库契约回归（2026-09-13，w-32314d00，错误事件 e22c1dc2）

事故：`POST /api/strategies/stop/{id}`（及 update/delete 同类）连续 500 ——
日志 `Error updating Strategy: Class 'builtins.str' is not mapped`。

根因：`StrategyORMRepository` 继承了 `BaseORMRepository.update(obj, commit)` / `delete(obj, commit)`，
而 `StrategyCodeService` 按**字典 API** 调用 `update(strategy_id, updates)` / `delete(strategy_id)`——
方法名撞车，参数被当成 ORM 对象：`session.merge("163")` → UnmappedInstanceError，
被基类 except 吞掉并打成 "Error updating Strategy"（返回 None → 路由 500）。

修复：仓库补 `update_user_strategy/delete_user_strategy`（写 quant.strategy_configs），服务改调它们。
本测试用假仓库锁住"服务必须调用显式命名的用户策略方法"，并对通用 update/delete 设绊线。
"""
from application.services.strategy_code_service import StrategyCodeService


class _FakeRepo:
    """只提供用户策略字典 API；通用 update/delete 设成绊线。"""

    def __init__(self):
        self.calls = []

    def get_by_id(self, strategy_id):
        return {
            'id': strategy_id,
            'strategy_name': 'probe',
            'code_type': 'indicator',
            'is_active': True,
            'metadata': {},
        }

    def update_user_strategy(self, strategy_id, updates):
        self.calls.append(('update_user_strategy', strategy_id, dict(updates)))
        return True

    def delete_user_strategy(self, strategy_id):
        self.calls.append(('delete_user_strategy', strategy_id))
        return True

    def update(self, *args, **kwargs):
        raise AssertionError('不应调用通用 update(obj, commit)——会 merge 字符串')
    delete = update


def _service(repo):
    return StrategyCodeService(strategy_repo=repo)


def test_stop_calls_update_user_strategy():
    repo = _FakeRepo()
    ok = _service(repo).update_strategy(strategy_id=163, is_active=False)
    assert ok is True
    assert repo.calls == [('update_user_strategy', 163, {'is_active': False})]


def test_delete_calls_delete_user_strategy():
    repo = _FakeRepo()
    assert _service(repo).delete_strategy(163) is True
    assert repo.calls == [('delete_user_strategy', 163)]


def test_update_never_touches_generic_crud():
    """绊线：服务一旦退回 repo.update(...) 会在这里炸，而不是线上 500。"""
    repo = _FakeRepo()
    _service(repo).update_strategy(strategy_id=163, description='x', is_public=True)
    _service(repo).delete_strategy(163)
    assert all(c[0] in ('update_user_strategy', 'delete_user_strategy') for c in repo.calls)


def test_user_strategy_whitelist_rejects_unknown_columns():
    """仓库白名单必须挡住不存在的列（元数据列名是 metadata，不是 strategy_metadata）。"""
    from adapters.outbound.repositories.strategy_repository import StrategyORMRepository as R
    assert 'metadata' in R.USER_STRATEGY_UPDATABLE
    assert 'is_active' in R.USER_STRATEGY_UPDATABLE
    assert 'risk_config' in R.USER_STRATEGY_UPDATABLE
    assert 'code_content' in R.USER_STRATEGY_UPDATABLE
    assert 'not_a_column' not in R.USER_STRATEGY_UPDATABLE
