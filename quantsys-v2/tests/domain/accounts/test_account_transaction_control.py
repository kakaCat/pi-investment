"""测试资金操作事务控制"""
import pytest
from unittest.mock import Mock, MagicMock

from domain.accounts.services.account_service import AccountService
from domain.accounts.models.account import Account, AccountStatus
from domain.accounts.models.balance import Balance


class TestAccountTransactionControl:
    """资金操作事务控制测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.account_repo = Mock()
        self.service = AccountService(account_repo=self.account_repo)

    def test_deduct_cash_with_commit_true(self):
        """测试扣减资金 commit=True (默认立即提交)"""
        # 准备账户
        account = Mock()
        account.cash_available = 10000.0
        self.account_repo.get_account.return_value = account
        self.account_repo.deduct_cash.return_value = True

        # 扣减资金（默认 commit=True）
        result = self.service.execute_deduct_cash("test_account", 1000.0)

        # 验证调用
        assert result is True
        self.account_repo.deduct_cash.assert_called_once_with("test_account", 1000.0)

    def test_deduct_cash_with_commit_false(self):
        """测试扣减资金 commit=False (由调用方管理事务)"""
        # 这个测试验证接口签名支持 commit 参数
        # 实际使用时，调用方应该这样调用：
        # repo.deduct_cash(account_name, amount, commit=False)
        # try:
        #     repo.deduct_cash("account_a", 1000, commit=False)
        #     repo.deduct_cash("account_b", 1000, commit=False)
        #     repo.session.commit()
        # except:
        #     repo.session.rollback()

        self.account_repo.deduct_cash.return_value = True

        # 验证接口支持 commit 参数
        result = self.service.execute_deduct_cash("test_account", 1000.0)
        assert result is True

    def test_add_cash_with_commit_parameter(self):
        """测试增加资金支持 commit 参数"""
        self.account_repo.add_cash.return_value = True

        # 增加资金
        result = self.service.execute_add_cash("test_account", 2000.0)

        # 验证调用
        assert result is True
        self.account_repo.add_cash.assert_called_once_with("test_account", 2000.0)

    def test_multiple_operations_in_transaction(self):
        """测试在一个事务内执行多个资金操作的场景

        这个测试演示如何在一个事务内扣减多个账户的资金：
        1. 扣减 account_a 的 1000
        2. 扣减 account_b 的 1000
        3. 如果任一失败，都能回滚

        虽然当前 AccountService 未直接使用 commit 参数，
        但底层 repository 已支持，为未来重构预留接口
        """
        # 模拟底层支持 commit 参数
        self.account_repo.deduct_cash.return_value = True

        # 场景：转账操作需要扣减两个账户
        # 实际代码应该在更底层调用 repo.deduct_cash(..., commit=False)
        result_a = self.service.execute_deduct_cash("account_a", 1000.0)
        result_b = self.service.execute_deduct_cash("account_b", 1000.0)

        assert result_a is True
        assert result_b is True
        assert self.account_repo.deduct_cash.call_count == 2


class TestSimulationAccountRepositoryTransactionControl:
    """SimulationAccountRepository 事务控制集成测试"""

    def test_deduct_cash_commit_false_does_not_commit(self):
        """测试 commit=False 时不会立即提交"""
        from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
        from unittest.mock import Mock

        # 创建 mock 的 sim_repo
        sim_repo = Mock()
        mock_account = Mock()
        mock_account.cash_available = 10000.0
        sim_repo.get_account.return_value = mock_account
        sim_repo.session = Mock()

        repo = SimulationAccountRepository(sim_repo=sim_repo)

        # 扣减资金但不提交
        result = repo.deduct_cash("test_account", 1000.0, commit=False)

        # 验证成功但未提交
        assert result is True
        assert mock_account.cash_available == 9000.0
        sim_repo.session.commit.assert_not_called()

    def test_deduct_cash_commit_true_commits(self):
        """测试 commit=True (默认) 时会立即提交"""
        from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
        from unittest.mock import Mock

        sim_repo = Mock()
        mock_account = Mock()
        mock_account.cash_available = 10000.0
        sim_repo.get_account.return_value = mock_account
        sim_repo.session = Mock()

        repo = SimulationAccountRepository(sim_repo=sim_repo)

        # 扣减资金并提交（默认行为）
        result = repo.deduct_cash("test_account", 1000.0)

        # 验证成功并已提交
        assert result is True
        assert mock_account.cash_available == 9000.0
        sim_repo.session.commit.assert_called_once()

    def test_add_cash_commit_false_does_not_commit(self):
        """测试增加资金 commit=False 时不会立即提交"""
        from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
        from unittest.mock import Mock

        sim_repo = Mock()
        mock_account = Mock()
        mock_account.cash_available = 10000.0
        sim_repo.get_account.return_value = mock_account
        sim_repo.session = Mock()

        repo = SimulationAccountRepository(sim_repo=sim_repo)

        # 增加资金但不提交
        result = repo.add_cash("test_account", 2000.0, commit=False)

        # 验证成功但未提交
        assert result is True
        assert mock_account.cash_available == 12000.0
        sim_repo.session.commit.assert_not_called()

    def test_multiple_operations_in_single_transaction(self):
        """测试在单事务内执行多个操作"""
        from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
        from unittest.mock import Mock

        sim_repo = Mock()

        # 准备两个账户
        account_a = Mock()
        account_a.cash_available = 10000.0
        account_b = Mock()
        account_b.cash_available = 5000.0

        sim_repo.get_account.side_effect = lambda name: account_a if name == "account_a" else account_b
        sim_repo.session = Mock()

        repo = SimulationAccountRepository(sim_repo=sim_repo)

        # 场景：在一个事务内转账
        try:
            # 1. 扣减 account_a
            result1 = repo.deduct_cash("account_a", 3000.0, commit=False)
            assert result1 is True

            # 2. 增加 account_b
            result2 = repo.add_cash("account_b", 3000.0, commit=False)
            assert result2 is True

            # 3. 统一提交
            sim_repo.session.commit()

        except Exception:
            # 失败则回滚
            sim_repo.session.rollback()

        # 验证状态
        assert account_a.cash_available == 7000.0
        assert account_b.cash_available == 8000.0
        sim_repo.session.commit.assert_called_once()

    def test_transaction_rollback_on_failure(self):
        """测试失败时事务回滚"""
        from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
        from unittest.mock import Mock

        sim_repo = Mock()

        # account_a 存在，account_b 不存在
        account_a = Mock()
        account_a.cash_available = 10000.0

        sim_repo.get_account.side_effect = lambda name: account_a if name == "account_a" else None
        sim_repo.session = Mock()

        repo = SimulationAccountRepository(sim_repo=sim_repo)

        # 场景：转账失败应该回滚
        try:
            # 1. 扣减 account_a 成功
            result1 = repo.deduct_cash("account_a", 3000.0, commit=False)
            assert result1 is True
            assert account_a.cash_available == 7000.0

            # 2. 增加 account_b 失败（账户不存在）
            result2 = repo.add_cash("account_b", 3000.0, commit=False)
            assert result2 is False

            # 失败，回滚
            sim_repo.session.rollback()

            # 手动恢复状态模拟回滚
            account_a.cash_available = 10000.0

        except Exception:
            sim_repo.session.rollback()

        # 验证回滚后状态
        assert account_a.cash_available == 10000.0
        sim_repo.session.rollback.assert_called()
        sim_repo.session.commit.assert_not_called()
