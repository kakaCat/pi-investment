"""账户状态管理测试"""
import uuid

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from infrastructure.persistence.orm.models.simulation import SimulationCashFlow


def test_set_account_status_roundtrip():
    repo = SimulationORMRepository()
    name = f'test_status_{uuid.uuid4().hex[:8]}'
    repo.create_account(account_name=name, initial_capital=10000)
    try:
        assert repo.set_account_status(name, 'frozen') is True
        assert repo.get_account(name).status == 'frozen'

        assert repo.set_account_status(name, 'active') is True
        assert repo.get_account(name).status == 'active'
    finally:
        #开户同时写账户行+deposit流水，两表都清；否则每跑一次残留一对
        #孤儿行（quant_test 曾积攒 27 个 test_status_* 账户）
        repo.session.query(SimulationCashFlow).filter_by(account_name=name).delete()
        acct = repo.get_account(name)
        if acct is not None:
            repo.session.delete(acct)
        repo.session.commit()


def test_set_account_status_nonexistent():
    repo = SimulationORMRepository()
    assert repo.set_account_status('no_such_account_xyz', 'frozen') is False
