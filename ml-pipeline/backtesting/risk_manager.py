"""风险管理器"""


class RiskManager:
    def __init__(
        self,
        stop_loss: float = 0.05,
        take_profit: float = 0.10,
        max_position: float = 0.3,
    ):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_position = max_position

    def should_stop_loss(self, buy_price: float, current_price: float) -> bool:
        return (current_price - buy_price) / buy_price < -self.stop_loss

    def should_take_profit(self, buy_price: float, current_price: float) -> bool:
        return (current_price - buy_price) / buy_price > self.take_profit

    def calculate_position_size(self, capital: float, price: float) -> float:
        return (capital * self.max_position) / price
