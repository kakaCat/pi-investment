"""
ORM Session 请求级清理测试（teardown）

回归背景：
Flask 请求线程通过 scoped_session 懒加载 Session，首个查询开启事务后
从不关闭 → 连接以 "idle in transaction" 状态永久占用连接池 → 池耗尽后
新请求阻塞至 pool_timeout（默认 30s）才失败或等待空位，表现为接口随机
卡顿 ~30s（实测 /api/game/pools/{id}/battlefield-assessment 30.07s）。

修复：每个请求结束时（teardown_appcontext）自动调用 close_session()。
"""
import pytest
from flask import Flask

from infrastructure.persistence.orm.config import (
    close_orm,
    get_session,
    init_orm,
    register_session_teardown,
)


@pytest.fixture()
def orm_sqlite():
    """用 sqlite 内存库初始化 ORM（无需 PostgreSQL），结束后复位全局状态"""
    close_orm()  # 防止被其他测试的初始化状态污染
    init_orm(dsn="sqlite:///:memory:", pool_size=2, max_overflow=1)
    yield
    close_orm()


def _make_app(register_teardown: bool) -> Flask:
    app = Flask(__name__)
    if register_teardown:
        register_session_teardown(app)

    @app.route("/touch")
    def touch():
        # 模拟请求处理中使用 ORM（懒加载当前线程的 Session）
        get_session()
        return "ok"

    return app


class TestSessionTeardown:
    def test_request_without_teardown_leaks_session(self, orm_sqlite):
        """未注册 teardown 时：跨请求复用同一个 Session（泄漏现状）"""
        client = _make_app(register_teardown=False).test_client()

        client.get("/touch")
        first = get_session()
        client.get("/touch")
        second = get_session()

        assert first is second  # 同一 Session 被两个请求复用 = 泄漏

    def test_request_with_teardown_releases_session(self, orm_sqlite):
        """注册 teardown 后：每个请求结束都移除 Session，连接归还连接池"""
        client = _make_app(register_teardown=True).test_client()

        client.get("/touch")
        first = get_session()
        client.get("/touch")
        second = get_session()

        assert first is not second  # 旧 Session 已被 teardown 移除
