# domain/portfolio/services/position_service.py
from typing import Optional, List
import structlog
from domain.portfolio.models.position import Position
from domain.portfolio.ports.IPositionRepository import IPositionRepository

logger = structlog.get_logger(__name__)

class PositionService:
    """持仓服务 - 管理股票持仓"""
    
    def __init__(self, position_repo: IPositionRepository):
        self.position_repo = position_repo
    
    def get_position(
        self,
        account_name: str,
        symbol: str,
    ) -> Optional[Position]:
        """获取单只股票持仓"""
        return self.position_repo.get_position(account_name, symbol)
    
    def get_all_positions(self, account_name: str) -> List[Position]:
        """获取账户所有持仓"""
        return self.position_repo.get_all_positions(account_name)
    
    def get_available_shares(
        self,
        account_name: str,
        symbol: str,
    ) -> int:
        """获取可卖股数（T+1规则）"""
        position = self.get_position(account_name, symbol)
        if not position:
            return 0
        return position.shares_available
    
    def update_on_buy(
        self,
        account_name: str,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        transfer_fee: float = 0.0,
    ) -> bool:
        """买入后更新持仓
        
        T+1规则：当日买入的 shares_available 不变（仍为0或原值），
        次日结算后才增加。
        """
        existing = self.get_position(account_name, symbol)
        
        if existing:
            # 加仓：计算新的移动加权平均成本
            old_qty = existing.shares_total
            old_cost = existing.avg_cost * old_qty
            new_qty = old_qty + quantity
            # 成本 = 旧成本 + 新买入金额 + 手续费
            new_cost = old_cost + price * quantity + commission + transfer_fee
            avg_cost = new_cost / new_qty if new_qty > 0 else 0
            
            # T+1: shares_available 不变
            shares_available = existing.shares_available
        else:
            # 建仓
            new_qty = quantity
            avg_cost = (price * quantity + commission + transfer_fee) / quantity
            # T+1: 当日买入不可卖
            shares_available = 0
        
        success = self.position_repo.upsert_position(
            account_name=account_name,
            symbol=symbol,
            shares_total=new_qty,
            avg_cost=avg_cost,
            shares_available=shares_available,
            current_price=price,
        )
        
        if success:
            action = "加仓" if existing else "建仓"
            logger.info(
                f"持仓已更新: {account_name} {symbol} "
                f"{action} {quantity}股 @ {price}, "
                f"total={new_qty}, available={shares_available} (T+1)"
            )
        
        return success
    
    def update_on_sell(
        self,
        account_name: str,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        stamp_duty: float = 0.0,
        transfer_fee: float = 0.0,
    ) -> bool:
        """卖出后更新持仓"""
        existing = self.get_position(account_name, symbol)
        
        if not existing:
            logger.warning(f"卖出但无持仓: {account_name} {symbol}")
            return False
        
        remaining = existing.shares_total - quantity
        
        if remaining <= 0:
            # 清仓
            success = self.position_repo.delete_position(account_name, symbol)
            if success:
                logger.info(
                    f"持仓已清仓: {account_name} {symbol} "
                    f"卖出 {quantity}股 @ {price}"
                )
            return success
        else:
            # 减仓：保持 avg_cost 不变
            new_available = max(0, existing.shares_available - quantity)
            success = self.position_repo.upsert_position(
                account_name=account_name,
                symbol=symbol,
                shares_total=remaining,
                avg_cost=existing.avg_cost,
                shares_available=new_available,
                current_price=price,
            )
            if success:
                logger.info(
                    f"持仓已减仓: {account_name} {symbol} "
                    f"卖出 {quantity}股 @ {price}, "
                    f"剩余 total={remaining}, available={new_available}"
                )
            return success
