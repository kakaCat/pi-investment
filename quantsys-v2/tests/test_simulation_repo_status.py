"""账户状态管理测试"""
import uuid

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository


def test_set_account_status_roundtrip():
    repo = SimulationORMRepository()
    name = f'test_status_{uuid.uuid4().hex[:8]}'
    repo.create_account(account_name=name, initial_capital=10000)

    assert repo.set_account_status(name, 'frozen') is True
    assert repo.get_account(name).status == 'frozen'

    assert repo.set_account_status(name, 'active') is True
    assert repo.get_account(name).status == 'active'


def test_set_account_status_nonexistent():
    repo = SimulationORMRepository()
    assert repo.set_account_status('no_such_account_xyz', 'frozen') is False
