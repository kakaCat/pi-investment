"""Tests for StockPoolORMRepository CRUD operations."""
import json
import pytest
from adapters.outbound.repositories import StockPoolORMRepository


@pytest.fixture
def repo():
    r = StockPoolORMRepository()
    # Clean up before each test
    cursor = r.db.cursor()
    cursor.execute("DELETE FROM quant.stock_pools")
    cursor.close()
    r.db.commit()
    return r


class TestStockPoolORMRepository:
    def test_create_static_pool(self, repo):
        pool = repo.create({
            'name': '测试静态池',
            'pool_type': 'static',
            'description': '单元测试用',
            'symbols': ['600519.SH', '000858.SZ'],
        })
        assert pool['id'] > 0
        assert pool['name'] == '测试静态池'
        assert pool['pool_type'] == 'static'
        assert pool['symbols'] == ['600519.SH', '000858.SZ']
        assert pool['filter_template'] is None

    def test_create_dynamic_pool(self, repo):
        template = {'min_score': 60, 'fundamental': ['pe_low'], 'top_n': 20}
        pool = repo.create({
            'name': '测试动态池',
            'pool_type': 'dynamic',
            'symbols': ['600519.SH'],
            'filter_template': template,
            'refresh_interval': 'weekly',
        })
        assert pool['pool_type'] == 'dynamic'
        assert pool['filter_template'] == template
        assert pool['refresh_interval'] == 'weekly'

    def test_get_by_id(self, repo):
        created = repo.create({
            'name': 'get测试',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        fetched = repo.get_by_id(created['id'])
        assert fetched is not None
        assert fetched['name'] == 'get测试'

    def test_get_by_id_not_found(self, repo):
        result = repo.get_by_id(99999)
        assert result is None

    def test_get_all(self, repo):
        repo.create({'name': '池1', 'pool_type': 'static', 'symbols': ['600519.SH']})
        repo.create({'name': '池2', 'pool_type': 'dynamic', 'symbols': ['000858.SZ'],
                      'filter_template': {'min_score': 50}, 'refresh_interval': 'daily'})
        pools = repo.get_all()
        assert len(pools) == 2

    def test_update(self, repo):
        created = repo.create({
            'name': '更新前',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        updated = repo.update(created['id'], {
            'name': '更新后',
            'symbols': ['600519.SH', '000001.SZ'],
            'description': '已更新',
        })
        assert updated['name'] == '更新后'
        assert len(updated['symbols']) == 2
        assert updated['description'] == '已更新'

    def test_update_not_found(self, repo):
        result = repo.update(99999, {'name': '不存在'})
        assert result is None

    def test_delete(self, repo):
        created = repo.create({
            'name': '待删除',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        assert repo.delete(created['id']) is True
        assert repo.get_by_id(created['id']) is None

    def test_delete_not_found(self, repo):
        assert repo.delete(99999) is False

    def test_update_symbols(self, repo):
        created = repo.create({
            'name': '符号更新',
            'pool_type': 'dynamic',
            'symbols': ['600519.SH'],
            'filter_template': {'min_score': 60},
            'refresh_interval': 'daily',
        })
        updated = repo.update_symbols(created['id'], ['000001.SZ', '000002.SZ'])
        assert updated['symbols'] == ['000001.SZ', '000002.SZ']
        assert updated['last_refreshed_at'] is not None

    def test_update_validation(self, repo):
        created = repo.create({
            'name': '验证更新',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        validation = {
            'validated_at': '2026-06-01T10:00:00',
            'best_strategy': {'id': 53, 'score': 82.5},
        }
        updated = repo.update_validation(created['id'], validation)
        assert updated['last_validation']['best_strategy']['id'] == 53

    def test_get_dynamic_pools(self, repo):
        repo.create({'name': '静态', 'pool_type': 'static', 'symbols': ['600519.SH']})
        repo.create({'name': '动态', 'pool_type': 'dynamic', 'symbols': ['000858.SZ'],
                      'filter_template': {'min_score': 50}, 'refresh_interval': 'daily'})
        dynamic = repo.get_dynamic_pools()
        assert len(dynamic) == 1
        assert dynamic[0]['pool_type'] == 'dynamic'
