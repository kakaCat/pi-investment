"""
V13策略模拟交易系统 - 主执行脚本（完整版）

功能：
1. 训练XGBoost模型
2. 每日检查是否需要调仓
3. 获取最新数据并计算85个因子
4. 模型预测Top 5股票
5. 执行模拟交易
6. 生成监控报告
"""

import os
# 必须在所有导入之前设置，避免 OpenMP/MKL 与 XGBoost 冲突导致段错误
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量（必须在导入其他模块之前）
load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.services.data_service import DataService
from live_trading.factor_calculator import V13FactorCalculator
from live_trading.v14_factor_calculator import V14FactorCalculator

# 因子计算器注册表：新策略引入全新因子体系时在此注册一行
FACTOR_CALCULATORS = {
    'v13': V13FactorCalculator,
    'v14': V14FactorCalculator,
}
from live_trading.simulation_broker import SimulationBroker
from adapters.outbound.repositories import SimulationORMRepository
from live_trading.v13_factors import get_factor_names
from live_trading.risk_control import RiskController
from infrastructure.persistence.database.engine import init_engine, get_engine

# 可选依赖：飞书通知（如果导入失败则禁用）
try:
    from utils.feishu_notifier import create_notifier_from_config
except ImportError:
    def create_notifier_from_config(config):
        logging.warning("feishu_notifier not available, notifications disabled")
        return None

import xgboost as xgb
import psycopg2


def judge_trading_day(day, *, kline_exists_on_date, latest_kline_date, today):
    """判定某天是否为交易日（纯函数，可单测）。

    语义（2026-08-12 重写，修复"盘中永远判定非交易日"bug）：
    - 周末 → False
    - 未来日期 → False
    - 当天日K已落库 → True（历史日期的主要判据，精确覆盖法定节假日）
    - 当天日K未落库且判定对象就是"今天"：盘中场景（日K 17:40 才更新），
      只要市场近期活跃（7 个自然日内有K线）→ True
    - 其他（过去的工作日无K线 = 节假日；长期停市/数据断供）→ False

    Args:
        day: 待判定日期（datetime.date）
        kline_exists_on_date: 该日期 daily_klines 是否有记录
        latest_kline_date: daily_klines 最大 trade_date（date 或 None）
        today: 今天（datetime.date）
    """
    if day.weekday() >= 5:
        return False
    if day > today:
        return False
    if kline_exists_on_date:
        return True
    if day == today:
        if latest_kline_date is None:
            return False
        return (today - latest_kline_date).days <= 7
    return False


class SimulationTrader:
    """V13策略模拟交易器（使用数据库持久化）"""

    def __init__(self, config_path='live_trading/config_simulation.yaml',
                 account_name='default', factor_calculator='v13'):
        """初始化

        Args:
            config_path: 交易参数配置文件路径
            account_name: 数据库账户名（必须在 _load_account_from_db 之前确定）
            factor_calculator: 因子计算器，FACTOR_CALCULATORS 注册表键名或实例
        """
        self.config = self._load_config(config_path)
        self.ds = DataService()

        # 因子计算器：注册表键名或直接传实例
        if isinstance(factor_calculator, str):
            if factor_calculator not in FACTOR_CALCULATORS:
                raise ValueError(
                    f"未知 factor_calculator: {factor_calculator}，"
                    f"可用: {sorted(FACTOR_CALCULATORS)}"
                )
            self.factor_calc = FACTOR_CALCULATORS[factor_calculator]()
        else:
            self.factor_calc = factor_calculator

        self.broker = SimulationBroker(
            commission_rate=self.config['trading']['commission_rate'],
            slippage_rate=self.config['trading']['slippage_rate']
        )

        # 初始化 SQLAlchemy Engine(如果未初始化)
        try:
            get_engine()
        except RuntimeError:
            init_engine(pool_size=5, max_overflow=10)

        # 让 Repository 自己从 Engine 池获取连接
        self.repo = SimulationORMRepository()

        self.model = None
        self.valid_factors = None

        # 模型文件路径（load_model 读取，可在构造后由调用方覆盖）
        base_dir = Path(__file__).parent
        self.model_path = str(base_dir / 'models' / 'v13_model.json')
        self.factors_path = str(base_dir / 'models' / 'valid_factors.json')

        # 账户名称（必须在 _load_account_from_db 之前赋值）
        self.account_name = account_name

        # 初始化风险控制
        self.risk_controller = RiskController(self.config['risk_control'])

        # 初始化飞书通知
        self.feishu_notifier = create_notifier_from_config(self.config)

        # 设置日志
        self._setup_logging()

        # 从数据库加载账户状态
        self._load_account_from_db()

        logging.info(f"V13模拟交易系统初始化完成（数据库模式）")
        logging.info(f"当前资金: ¥{self.cash:,.2f}")
        if self.feishu_notifier:
            logging.info("飞书通知已启用")

    def _load_config(self, config_path):
        """加载配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        """设置日志"""
        from infrastructure.logging import configure_structured_logging
        import structlog

        log_dir = Path(self.config['logging']['log_dir'])
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"simulation_{datetime.now().strftime('%Y%m%d')}.log"

        # 使用结构化日志配置
        configure_structured_logging(
            level=self.config['logging']['level'],
            json_format=False,
            enable_trace_id=True
        )

        # 添加文件处理器（保留文件日志功能）
        import logging
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logging.getLogger().addHandler(file_handler)

    def _load_account_from_db(self):
        """从数据库加载账户状态"""
        account = self.repo.get_account(self.account_name)

        if account:
            # 兼容ORM对象和dict
            if hasattr(account, 'cash_available'):
                # ORM对象
                self.cash = float(account.cash_available or 0) + float(account.cash_frozen or 0)
                self.peak_value = float(account.peak_value)
                self.last_rebalance_date = str(account.last_rebalance_date) if account.last_rebalance_date else None
            else:
                # dict
                self.cash = float(account.get('cash_available', 0) or 0) + float(account.get('cash_frozen', 0) or 0)
                self.peak_value = float(account['peak_value'])
                self.last_rebalance_date = str(account['last_rebalance_date']) if account['last_rebalance_date'] else None

            # ✅ 从交易记录重建持仓（单一数据源）
            self.portfolio = self._rebuild_portfolio_from_trades()

            # 验证持仓表一致性
            db_positions = self.repo.get_all_positions(self.account_name)
            db_count = len(db_positions)
            real_count = len(self.portfolio)

            if db_count != real_count:
                logging.warning(f"⚠️ 持仓不一致: 数据库{db_count}只 vs 交易记录{real_count}只")
                logging.warning(f"   将在调仓后自动修复")

            logging.info(f"从数据库加载账户: {len(self.portfolio)}只持仓（从交易记录重建）")
        else:
            # 初始化账户
            self.cash = self.config['initial_capital']
            self.peak_value = self.cash
            self.last_rebalance_date = None
            self.portfolio = {}
            logging.info(f"初始化新账户: ¥{self.cash:,.2f}")

    def _rebuild_portfolio_from_trades(self):
        """从交易记录重建持仓（单一数据源）"""
        from infrastructure.persistence.database.engine import get_engine

        engine = get_engine()
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()

            # 2026-08-12：action 用 UPPER() 匹配——历史上 AccountTradingService
            # 写入过小写 'buy'/'sell'（8/5 三笔卖出因此被无视 → 幽灵持仓注水估值）。
            # 写入侧已由 repo.normalize_action 统一大写，此处兼容存量脏数据。
            query = '''
                SELECT
                    symbol,
                    SUM(CASE WHEN UPPER(action) = 'BUY' THEN shares
                             WHEN UPPER(action) = 'SELL' THEN -shares
                             ELSE 0 END) as total_shares,
                    SUM(CASE WHEN UPPER(action) = 'BUY' THEN shares * filled_price END) /
                    NULLIF(SUM(CASE WHEN UPPER(action) = 'BUY' THEN shares END), 0) as avg_price
                FROM quant.simulation_trades
                WHERE account_name = %s
                GROUP BY symbol
                HAVING SUM(CASE WHEN UPPER(action) = 'BUY' THEN shares
                                WHEN UPPER(action) = 'SELL' THEN -shares
                                ELSE 0 END) > 0
            '''

            cursor.execute(query, (self.account_name,))
            rows = cursor.fetchall()
            cursor.close()

            portfolio = {}
            for row in rows:
                if isinstance(row, dict):
                    symbol = row['symbol']
                    shares = int(row['total_shares'])
                    avg_price = float(row['avg_price'])
                else:
                    symbol = row[0]
                    shares = int(row[1])
                    avg_price = float(row[2])

                portfolio[symbol] = {
                    'shares': shares,
                    'avg_price': avg_price
                }

            logging.info(f"从交易记录重建持仓: {len(portfolio)}只股票")
            return portfolio
        finally:
            conn.close()  # 确保连接归还到池

    def _validate_data_consistency(self):
        """调仓前数据一致性检查"""
        logging.info("\n数据一致性检查...")

        # 1. 从交易记录计算真实持仓
        real_portfolio = self._rebuild_portfolio_from_trades()

        # 2. 检查数据库持仓表
        db_positions = self.repo.get_all_positions(self.account_name)
        db_symbols = set()
        for pos in db_positions:
            symbol = pos.symbol if hasattr(pos, 'symbol') else pos['symbol']
            db_symbols.add(symbol)

        # 3. 对比
        real_symbols = set(real_portfolio.keys())
        missing = real_symbols - db_symbols
        extra = db_symbols - real_symbols

        if missing or extra:
            logging.warning(f"⚠️ 数据不一致！")
            if missing:
                logging.warning(f"   缺失持仓: {missing}")
            if extra:
                logging.warning(f"   多余持仓: {extra}")
            logging.warning(f"   自动修复中...")

            # 自动修复：清空并重建
            self.repo.clear_all_positions(self.account_name)
            for symbol, pos in real_portfolio.items():
                self.repo.upsert_position(
                    account_name=self.account_name,
                    symbol=symbol,
                    shares_total=pos['shares'],
                    avg_cost=pos['avg_price']
                )
            logging.info(f"✅ 已自动修复持仓表")
        else:
            logging.info(f"✅ 数据一致性检查通过（{len(real_symbols)}只持仓）")

        # 4. 更新内存持仓
        self.portfolio = real_portfolio

    def _save_account_to_db(self):
        """保存账户状态到数据库"""
        # ✅ 从交易记录重建持仓，确保数据一致性
        self.portfolio = self._rebuild_portfolio_from_trades()

        total_value = self._calculate_total_value_from_portfolio()
        cumulative_return = (total_value / self.config['initial_capital'] - 1)
        max_drawdown = (total_value / self.peak_value - 1) if self.peak_value > 0 else 0

        # ✅ 严重告警：检查现金是否为负（透支）
        if self.cash < 0:
            logging.error(f"🚨 严重警告：账户现金为负 ¥{self.cash:,.2f}！")
            logging.error(f"   初始资金: ¥{self.config['initial_capital']:,.2f}")
            logging.error(f"   总资产: ¥{total_value:,.2f}")
            logging.error(f"   透支金额: ¥{abs(self.cash):,.2f}")
            logging.error(f"   请立即检查交易记录，可能存在超买问题！")

        # ✅ 警告：检查总资产是否低于初始资金的50%
        if total_value < self.config['initial_capital'] * 0.5:
            logging.warning(f"⚠️  警告：总资产已跌破初始资金的50%")
            logging.warning(f"   当前总资产: ¥{total_value:,.2f}")
            logging.warning(f"   累计亏损: {cumulative_return:.2%}")

        position_value = total_value - self.cash
        self.repo.update_account(
            account_name=self.account_name,
            cash_available=self.cash,
            total_value=total_value,
            peak_value=self.peak_value,
            cumulative_return=cumulative_return,
            max_drawdown=max_drawdown,
            position_value=position_value,
            last_rebalance_date=self.last_rebalance_date
        )

        # ✅ 先清空持仓表，再重建（防止残留）
        self.repo.clear_all_positions(self.account_name)

        # 保存持仓
        for symbol, pos in self.portfolio.items():
            self.repo.upsert_position(
                account_name=self.account_name,
                symbol=symbol,
                shares_total=pos['shares'],
                avg_cost=pos['avg_price']
            )

        # T+1 结转：当日买入的份额当日不可卖
        self.repo.settle_t1(self.account_name)

        # ✅ 保存每日快照（按账户隔离，写入 simulation_equity_snapshot）
        self._save_daily_snapshot(total_value, cumulative_return)

    def _save_daily_snapshot(self, total_value: float, cumulative_return: float):
        """保存每日账户快照到 simulation_equity_snapshot 表（按账户隔离）

        修复：旧实现写 quant.account_balance（无账户列），多账户同日互相覆盖。
        """
        position_value = total_value - self.cash
        drawdown = (total_value / self.peak_value - 1) if self.peak_value > 0 else 0
        self.repo.upsert_equity_snapshot(
            self.account_name,
            cash=self.cash,
            position_value=position_value,
            total_value=total_value,
            cumulative_return=cumulative_return,
            drawdown=drawdown,
        )
        logging.info(f"保存每日快照: {self.account_name}, 总资产=¥{total_value:,.2f}")

    def _calculate_total_value_from_portfolio(self):
        """从持仓计算总资产"""
        if not self.portfolio:
            return self.cash

        # 获取当前价格
        symbols = list(self.portfolio.keys())
        prices = {}
        for symbol in symbols:
            try:
                latest = self.ds.kline.get_latest_daily_kline(symbol)
                if latest is not None and not latest.is_empty():
                    prices[symbol] = float(latest['close'][0])
                else:
                    prices[symbol] = self.portfolio[symbol]['avg_price']
            except:
                prices[symbol] = self.portfolio[symbol]['avg_price']

        # 计算持仓市值
        portfolio_value = sum(
            self.portfolio[symbol]['shares'] * prices.get(symbol, self.portfolio[symbol]['avg_price'])
            for symbol in self.portfolio
        )

        return self.cash + portfolio_value

    def _get_stock_pool(self, limit=200):
        """
        获取创业板股票池

        过滤条件：
        1. 排除ST股票（财务异常、退市风险）
        2. 排除*ST股票（严重财务异常）
        3. 排除退市股票
        4. 日均成交额 >= 1亿（保证流动性，过滤超小盘股）
        """
        # 兼容ORM和非ORM Repository
        from infrastructure.persistence.database.engine import get_engine
        engine = get_engine()
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()

            query = f'''
                WITH latest_kline AS (
                    SELECT DISTINCT ON (symbol)
                        symbol,
                        close,
                        volume,
                        amount,
                        turnover_rate,
                        trade_date
                    FROM quant.daily_klines
                    WHERE trade_date >= CURRENT_DATE - INTERVAL '10 days'
                    ORDER BY symbol, trade_date DESC
                )
                SELECT s.symbol, s.name
                FROM quant.stocks s
                INNER JOIN latest_kline k ON s.symbol = k.symbol
                WHERE s.symbol LIKE '3%'
                  AND s.name NOT LIKE '%ST%'                    -- 排除所有ST股票
                  AND s.name NOT LIKE '*%'                      -- 排除退市整理股票
                  AND s.name NOT LIKE '%退%'                    -- 排除退市相关
                  AND k.amount >= 100000000                     -- 日成交额 >= 1亿
                  AND k.volume > 0                              -- 有成交量
                ORDER BY k.amount DESC                          -- 按成交额排序，优先流动性好的
                LIMIT {limit}
            '''

            cursor.execute(query)
            stocks = cursor.fetchall()
            cursor.close()

            # 处理字典或元组返回值
            if stocks and isinstance(stocks[0], dict):
                return [{'symbol': s['symbol'], 'name': s['name']} for s in stocks]
            else:
                return [{'symbol': s[0], 'name': s[1]} for s in stocks]
        finally:
            conn.close()  # 确保连接归还到池

    def _get_historical_data(self, symbols, start_date, end_date):
        """
        获取历史K线数据（用于模型训练）

        直接查询数据库，避免逐个调用get_latest()

        Args:
            symbols: 字符串列表 ['300001', '300002'] 或字典列表 [{'symbol': '300001'}, ...]
        """
        import pandas as pd

        logging.info(f"查询 {len(symbols)} 只股票，时间范围 {start_date} -> {end_date}")

        # 支持两种输入格式
        if isinstance(symbols[0], dict):
            symbol_list = [s['symbol'] for s in symbols]
        else:
            symbol_list = symbols

        placeholders = ','.join(['%s'] * len(symbol_list))

        # 兼容ORM和非ORM Repository
        from infrastructure.persistence.database.engine import get_engine
        engine = get_engine()
        conn = engine.raw_connection()
        try:
            cursor = conn.cursor()
            query = f'''
                SELECT
                    symbol,
                    trade_date as date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    COALESCE(turnover_rate, 0) as turnover_rate
                FROM quant.daily_klines
                WHERE symbol IN ({placeholders})
                  AND trade_date BETWEEN %s AND %s
                ORDER BY symbol, trade_date
            '''

            cursor.execute(query, symbol_list + [start_date, end_date])
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                logging.warning("未查询到任何K线数据")
                return pd.DataFrame()

            # 转换为DataFrame
            if isinstance(rows[0], dict):
                df = pd.DataFrame(rows)
            else:
                df = pd.DataFrame(rows, columns=['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'turnover_rate'])

            df['date'] = pd.to_datetime(df['date'])

            logging.info(f"获取到 {len(df)} 条K线数据，{df['symbol'].nunique()} 只股票")
            return df
        finally:
            conn.close()  # 确保连接归还到池

    def train_model(self, train_start='2025-06-01', train_end='2026-06-01', stock_limit=200, ic_threshold=0.005, xgb_params=None):
        """
        训练模型

        Args:
            train_start: 训练开始日期
            train_end: 训练结束日期
            stock_limit: 股票池大小（默认200只，提高模型泛化能力）
            ic_threshold: IC筛选阈值（默认0.005，保留更多因子）
            xgb_params: XGBoost自定义参数（dict），用于超参数优化
        """
        logging.info(f"开始训练模型: {train_start} -> {train_end}")
        logging.info(f"股票池大小: {stock_limit}只, IC阈值: {ic_threshold}")

        # 1. 获取股票池（扩大到200只）
        stocks = self._get_stock_pool(limit=stock_limit)
        logging.info(f"获取股票池: {len(stocks)}只")

        # 2. 获取训练数据（使用日期范围查询，不用get_latest）
        logging.info("获取训练数据...")
        train_data = self._get_historical_data(stocks, train_start, train_end)

        if train_data.empty:
            raise ValueError("训练数据为空")

        # 3. 计算因子
        logging.info("计算因子...")
        train_data = self.factor_calc.calculate_factors(train_data)

        # 4. 准备标签（未来5日收益）
        logging.info("准备标签...")
        train_data = train_data.sort_values(['symbol', 'date'])
        train_data['label'] = train_data.groupby('symbol')['close'].transform(
            lambda x: x.pct_change(5).shift(-5)
        )

        # 5. 筛选有效因子
        logging.info("筛选有效因子...")
        all_factors = get_factor_names()
        self.valid_factors = self._select_factors(train_data, all_factors, ic_threshold=ic_threshold)

        # 6. 训练模型
        logging.info("训练XGBoost模型...")
        train_clean = train_data.dropna(subset=['label'] + self.valid_factors)

        X_train = train_clean[self.valid_factors]
        y_train = train_clean['label']

        logging.info(f"训练数据: {len(train_clean)}条, {len(self.valid_factors)}个因子")
        logging.info(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")

        # 检查是否有无效值
        if X_train.isnull().any().any():
            logging.warning("X_train 包含 NaN 值")
        if y_train.isnull().any():
            logging.warning("y_train 包含 NaN 值")

        # 使用自定义参数或默认参数
        if xgb_params:
            logging.info(f"使用自定义XGBoost参数: {xgb_params}")
            default_params = {
                'objective': 'reg:squarederror',
                'random_state': 42,
                'n_jobs': 1  # 使用单线程避免段错误
            }
            default_params.update(xgb_params)
            self.model = xgb.XGBRegressor(**default_params)
        else:
            self.model = xgb.XGBRegressor(
                objective='reg:squarederror',
                max_depth=5,
                learning_rate=0.05,
                n_estimators=100,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=1  # 使用单线程避免段错误
            )

        logging.info("开始拟合模型...")
        self.model.fit(X_train, y_train, verbose=False)
        logging.info(f"模型训练完成: {len(train_clean)}条训练数据, {len(self.valid_factors)}个有效因子")

        # 7. 保存模型
        model_dir = Path('live_trading/models')
        model_dir.mkdir(parents=True, exist_ok=True)
        model_file = model_dir / 'v13_model.json'
        self.model.save_model(str(model_file))

        # 保存有效因子列表
        factors_file = model_dir / 'valid_factors.json'
        with open(factors_file, 'w') as f:
            json.dump(self.valid_factors, f)

        # 保存训练信息
        train_info = {
            'train_start': train_start,
            'train_end': train_end,
            'stock_count': len(stocks),
            'sample_count': len(train_clean),
            'factor_count': len(self.valid_factors),
            'train_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        info_file = model_dir / 'train_info.json'
        with open(info_file, 'w') as f:
            json.dump(train_info, f, indent=2)

        logging.info(f"模型已保存: {model_file}")
        logging.info(f"训练信息: {stock_limit}只股票, {len(train_clean)}条样本, {len(self.valid_factors)}个因子")

    def _select_factors(self, data, factors, ic_threshold=0.01):
        """
        筛选有效因子

        Args:
            data: 训练数据
            factors: 候选因子列表
            ic_threshold: IC阈值（默认0.01，更宽松以保留更多因子）

        Note:
            - 大样本量时，单因子IC会降低，但组合预测能力仍强
            - 使用0.01阈值平衡因子数量和质量
            - XGBoost会自动选择重要因子
        """
        ic_results = {}
        valid_data = data.dropna(subset=['label'])

        for factor in factors:
            if factor not in valid_data.columns:
                continue

            factor_data = valid_data[[factor, 'label']].dropna()

            if len(factor_data) < 100:
                continue

            # 检查因子是否为常数
            if factor_data[factor].std() < 1e-10:
                continue

            try:
                # 使用 pandas 的 corr 方法计算 Spearman 相关系数
                # 比 scipy.stats.spearmanr 更稳定
                ic = factor_data[factor].corr(factor_data['label'], method='spearman')

                if not np.isnan(ic) and np.isfinite(ic):
                    ic_results[factor] = ic
            except Exception as e:
                logging.debug(f"因子 {factor} 计算IC失败: {e}")
                continue

        # 筛选有效因子（降低阈值到0.01）
        valid_factors = [f for f, ic in ic_results.items() if abs(ic) > ic_threshold]

        logging.info(f"因子筛选: {len(valid_factors)}/{len(factors)}个有效 (IC阈值: {ic_threshold})")

        # 显示Top 10
        sorted_ics = sorted(ic_results.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
        for factor, ic in sorted_ics:
            logging.info(f"  {factor}: IC={ic:.4f}")

        return valid_factors

    def load_model(self):
        """加载已训练的模型（路径来自 self.model_path / self.factors_path）"""
        model_file = Path(self.model_path)
        factors_file = Path(self.factors_path)

        if not model_file.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_file}")
        if not factors_file.exists():
            raise FileNotFoundError(f"因子文件不存在: {factors_file}")

        self.model = xgb.XGBRegressor(n_jobs=1)  # 使用单线程避免段错误
        self.model.load_model(str(model_file))

        with open(factors_file, 'r') as f:
            self.valid_factors = json.load(f)

        logging.info(f"模型加载完成: {len(self.valid_factors)}个因子 ({model_file.name})")

    def _is_trading_day(self, date_str: str) -> bool:
        """
        判断是否是交易日

        Args:
            date_str: 日期字符串 'YYYY-MM-DD'

        Returns:
            bool: 是否是交易日

        2026-08-12 修复：旧实现用"当天日K是否已落库"作唯一判据，但日K 17:40
        才更新，盘中/早盘的调度检查（06:30/14:30/15:30）永远判定"今天不是
        交易日"→ v13/v14 调仓永远跳过且被记为 success。判定逻辑抽为纯函数
        judge_trading_day，这里只负责取数。
        """
        day = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = datetime.now().date()

        # 非周末的过去/当天日期才需要查库；周末和未来日纯函数即可判定
        if day.weekday() >= 5 or day > today:
            return judge_trading_day(
                day, kline_exists_on_date=False, latest_kline_date=None, today=today,
            )

        try:
            cursor = self.repo.session.connection().connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM quant.daily_klines
                WHERE trade_date = %s
                LIMIT 1
            """, (date_str,))
            kline_exists = cursor.fetchone()[0] > 0
            cursor.execute("SELECT MAX(trade_date) FROM quant.daily_klines")
            latest_kline_date = cursor.fetchone()[0]
            cursor.close()
            return judge_trading_day(
                day,
                kline_exists_on_date=kline_exists,
                latest_kline_date=latest_kline_date,
                today=today,
            )
        except Exception as e:
            logging.warning(f"检查交易日失败: {e}，默认周一至周五为交易日")
            # 如果数据库查询失败，默认周一到周五是交易日
            return day.weekday() < 5

    def _count_trading_days(self, start_date: str, end_date: str) -> int:
        """
        计算两个日期之间的交易日数量

        Args:
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'

        Returns:
            int: 交易日数量
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        count = 0
        current = start
        while current <= end:
            if self._is_trading_day(current.strftime('%Y-%m-%d')):
                count += 1
            current += timedelta(days=1)

        return count

    def _is_rebalance_due(self, current_date):
        """判断是否到达调仓周期（不含交易日校验）"""
        if self.last_rebalance_date is None:
            return True

        # 计算距离上次调仓的交易日天数
        trading_days = self._count_trading_days(self.last_rebalance_date, current_date)

        # 不包括起始日，所以减1
        trading_days -= 1

        return trading_days >= self.config['strategy']['rebalance_days']

    def should_rebalance(self, current_date):
        """判断是否需要调仓（交易日校验 + 调仓周期）"""
        # 1. 检查是否是交易日
        if not self._is_trading_day(current_date):
            logging.info(f"{current_date} 不是交易日，跳过检查")
            return False

        return self._is_rebalance_due(current_date)

    def run_daily_check(self):
        """每日检查（手动调用）

        Returns:
            dict: 执行结果（2026-08-12 起返回结构化结果，让调度层能区分
                  "执行了"和"跳过了"——此前跳过被记为 success 导致空转数周无人察觉）
                  - executed: False + reason（model_not_loaded / not_trading_day）
                  - executed: True + action（stop_loss / rebalance / hold）
        """
        today = datetime.now().strftime('%Y-%m-%d')
        logging.info(f"\n{'='*60}")
        logging.info(f"日期: {today}")
        logging.info(f"{'='*60}")

        # 检查模型
        if self.model is None:
            logging.error("模型未加载，请先训练或加载模型")
            return {'executed': False, 'reason': 'model_not_loaded'}

        # 交易日校验前置（此前埋在 should_rebalance 里，无法与"未到调仓周期"区分）
        if not self._is_trading_day(today):
            logging.info(f"{today} 不是交易日，跳过检查")
            return {'executed': False, 'reason': 'not_trading_day'}

        action = 'hold'

        # 1. 检查单股止损
        if self.portfolio:
            prices = self._get_current_prices(list(self.portfolio.keys()), today)
            stop_loss_symbols = self.risk_controller.check_single_stock_stop_loss(
                self.portfolio, prices
            )

            if stop_loss_symbols:
                logging.warning(f"触发单股止损: {stop_loss_symbols}")
                self._execute_stop_loss(stop_loss_symbols, prices, today)
                self._save_account_to_db()
                action = 'stop_loss'

        # 2. 检查是否需要调仓
        if not self._is_rebalance_due(today):
            last_date = datetime.strptime(self.last_rebalance_date, '%Y-%m-%d')
            days_passed = (datetime.now() - last_date).days
            days_to_next = self.config['strategy']['rebalance_days'] - days_passed
            logging.info(f"距离下次调仓还有 {days_to_next} 天")
            return {'executed': True, 'action': action, 'days_to_next': days_to_next}

        logging.info("触发调仓条件，开始执行...")
        self.rebalance(today)
        return {'executed': True, 'action': 'rebalance'}

    def rebalance(self, current_date):
        """执行调仓"""
        logging.info("\n" + "="*60)
        logging.info(f"开始调仓流程 (账户: {self.account_name})")
        logging.info("="*60)

        try:
            # ✅ 调仓前数据一致性检查
            self._validate_data_consistency()

            # 1. 获取股票池
            stocks = self._get_stock_pool(limit=200)
            logging.info(f"股票池: {len(stocks)}只")

            # 2. 获取最新因子
            logging.info("计算最新因子...")
            latest_factors = self.factor_calc.get_latest_factors(stocks)

            if latest_factors.empty:
                logging.error("因子计算失败，取消调仓")
                return {
                    'success': False,
                    'error': '因子计算失败',
                    'account_name': self.account_name
                }

            # 3. 模型预测
            logging.info("模型预测...")
            available_factors = [f for f in self.valid_factors if f in latest_factors.columns]

            if len(available_factors) < len(self.valid_factors) * 0.8:
                logging.warning(f"可用因子不足: {len(available_factors)}/{len(self.valid_factors)}")

            X_pred = latest_factors[available_factors].fillna(0)
            predictions = self.model.predict(X_pred)
            latest_factors['predicted_return'] = predictions

            # 4. 使用风险控制器选股
            top_stocks, weights = self.risk_controller.select_stocks(
                latest_factors[['symbol', 'predicted_return']],
                current_holdings=list(self.portfolio.keys())
            )
            logging.info(f"\n风控选股结果 (Top {len(top_stocks)}):")
            for symbol in top_stocks:
                pred = latest_factors[latest_factors['symbol'] == symbol]['predicted_return'].iloc[0]
                weight = weights[symbol]
                logging.info(f"  {symbol}: 预测收益={pred:.4f}, 权重={weight:.2%}")

            # 5. 计算当前状态
            total_value = self._calculate_total_value(current_date)
            current_return = (total_value / self.config['initial_capital'] - 1)

            # 更新峰值
            if total_value > self.peak_value:
                self.peak_value = total_value

            drawdown = (total_value / self.peak_value - 1)

            logging.info(f"\n当前状态:")
            logging.info(f"  总资产: ¥{total_value:,.2f}")
            logging.info(f"  累计收益: {current_return:.2%}")
            logging.info(f"  峰值回撤: {drawdown:.2%}")

            # 6. 使用风险控制器计算目标仓位
            position_scale = self.risk_controller.calculate_position_scale(
                current_value=total_value,
                peak_value=self.peak_value
            )
            logging.info(f"  目标仓位: {position_scale:.0%}")

            # 7. 执行交易（使用风控权重）
            self._execute_trades_with_risk_control(top_stocks, weights, position_scale, current_date)

            # 8. 更新状态
            self.last_rebalance_date = current_date
            self._save_account_to_db()

            # 9. 生成报告
            # self.generate_daily_report(current_date)  # 暂时注释，ORM Repository缺少get_latest_report

            # 10. 发送飞书通知
            if self.feishu_notifier:
                self._send_rebalance_notification(
                    current_date,
                    top_stocks,
                    weights,
                    latest_factors,
                    total_value
                )

            logging.info("\n调仓完成\n")

            # 返回调仓结果
            return {
                'success': True,
                'account_name': self.account_name,
                'date': current_date,
                'total_value': float(total_value),
                'positions': [{
                    'symbol': symbol,
                    'weight': float(weights[symbol])
                } for symbol in top_stocks],
                'position_count': len(top_stocks)
            }

        except Exception as e:
            logging.error(f"调仓失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'account_name': self.account_name
            }

    def _calculate_total_value(self, date):
        """计算总资产"""
        # 获取当前价格
        symbols = list(self.portfolio.keys())
        if not symbols:
            return self.cash

        prices = {}
        for symbol in symbols:
            try:
                df = self.ds.kline.get_stock_kline(
                    symbol=symbol,
                    start_date=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                    end_date=date
                )
                if not df.empty:
                    prices[symbol] = float(df.iloc[-1]['close'])
            except:
                prices[symbol] = self.portfolio[symbol]['avg_price']

        # 计算持仓市值
        portfolio_value = sum(
            self.portfolio[symbol]['shares'] * prices.get(symbol, self.portfolio[symbol]['avg_price'])
            for symbol in self.portfolio
        )

        return self.cash + portfolio_value

    def _execute_trades_with_risk_control(self, target_symbols, weights, position_scale, date):
        """执行交易（使用风险控制权重）"""
        target_symbols_set = set(target_symbols)

        logging.info(f"\n{'='*60}")
        logging.info(f"开始执行交易 (账户: {self.account_name})")
        logging.info(f"{'='*60}")
        logging.info(f"目标持仓: {len(target_symbols)}只 - {target_symbols}")
        logging.info(f"当前持仓: {len(self.portfolio)}只 - {list(self.portfolio.keys())}")
        logging.info(f"当前现金: ¥{self.cash:,.2f}")
        logging.info(f"目标仓位比例: {position_scale:.0%}")

        # 获取当前价格
        prices = self._get_current_prices(
            list(target_symbols_set | set(self.portfolio.keys())),
            date
        )
        logging.info(f"获取到{len(prices)}只股票价格")

        # 卖出不在目标中的股票
        for symbol in list(self.portfolio.keys()):
            if symbol not in target_symbols_set:
                shares = self.portfolio[symbol]['shares']

                # ✅ 防止重复卖出：检查持仓数量
                if shares <= 0:
                    logging.warning(f"跳过 {symbol}: 持仓数量={shares}，无需卖出")
                    del self.portfolio[symbol]
                    continue

                price = prices.get(symbol, self.portfolio[symbol]['avg_price'])

                # 模拟交易
                trade = self.broker.sell(symbol, shares, price)
                self.cash += trade['total_revenue']

                # 保存交易记录到数据库
                self.repo.add_trade(
                    account_name=self.account_name,
                    symbol=symbol,
                    action='SELL',
                    shares=shares,
                    price=price,
                    filled_price=trade['filled_price'],
                    amount=trade['amount'],
                    commission=trade['commission'],
                    stamp_duty=trade.get('stamp_duty', 0),
                    total_revenue=trade['total_revenue'],
                    trade_date=date
                )

                # 删除持仓
                del self.portfolio[symbol]
                self.repo.delete_position(self.account_name, symbol)

                logging.info(f"卖出 {symbol}: {shares}股 @ ¥{price:.2f}")

        # 计算总资产
        total_value = self.cash + sum(
            self.portfolio[s]['shares'] * prices.get(s, self.portfolio[s]['avg_price'])
            for s in self.portfolio
        )

        # ✅ 关键检查：买入前验证现金是否充足
        if self.cash <= 0:
            logging.error(f"❌ 现金不足（¥{self.cash:,.2f}），取消所有买入操作")
            logging.error(f"   可能原因：卖出收入不足以支付新的买入")
            return

        available_cash = self.cash
        logging.info(f"\n可用现金: ¥{available_cash:,.2f}")

        # 买入目标股票（使用风控权重）
        for symbol in target_symbols:
            weight = weights[symbol]
            target_value = total_value * weight * position_scale
            price = prices.get(symbol, 0)

            if price <= 0:
                logging.warning(f"跳过 {symbol}: 价格无效")
                continue

            target_shares = int(target_value / price / 100) * 100  # 100股整数倍

            if target_shares == 0:
                continue

            # 如果已持有，调整仓位
            current_shares = self.portfolio.get(symbol, {}).get('shares', 0)
            delta_shares = target_shares - current_shares

            if delta_shares > 0:
                # 买入
                cost = delta_shares * price * (1 + self.config['trading']['commission_rate'])

                # ✅ 严格检查：本次买入是否超出可用现金
                if cost > available_cash:
                    logging.warning(f"跳过 {symbol}: 需要¥{cost:,.2f}，剩余现金¥{available_cash:,.2f}")
                    continue

                if cost <= self.cash:
                    trade = self.broker.buy(symbol, delta_shares, price)
                    self.cash -= trade['total_cost']
                    available_cash -= trade['total_cost']  # ✅ 同步扣除可用现金

                    # 保存交易记录到数据库
                    self.repo.add_trade(
                    account_name=self.account_name,
                        symbol=symbol,
                        action='BUY',
                        shares=delta_shares,
                        price=price,
                        filled_price=trade['filled_price'],
                        amount=trade['amount'],
                        commission=trade['commission'],
                        stamp_duty=0,
                        total_revenue=-trade['total_cost'],
                        trade_date=date
                    )

                    # 更新持仓
                    if symbol in self.portfolio:
                        old_shares = self.portfolio[symbol]['shares']
                        old_avg = self.portfolio[symbol]['avg_price']
                        new_shares = old_shares + delta_shares
                        new_avg = (old_shares * old_avg + delta_shares * trade['filled_price']) / new_shares
                        self.portfolio[symbol] = {'shares': new_shares, 'avg_price': new_avg}
                    else:
                        self.portfolio[symbol] = {'shares': delta_shares, 'avg_price': trade['filled_price']}

                    logging.info(f"买入 {symbol}: {delta_shares}股 @ ¥{price:.2f} (权重{weight:.2%}，花费¥{trade['total_cost']:,.2f}，剩余¥{available_cash:,.2f})")
                else:
                    logging.warning(f"资金不足，无法买入 {symbol}")


            elif delta_shares < 0:
                # 卖出部分
                sell_shares = -delta_shares
                trade = self.broker.sell(symbol, sell_shares, price)
                self.cash += trade['total_revenue']

                # 保存交易记录
                self.repo.add_trade(
                    account_name=self.account_name,
                    symbol=symbol,
                    action='SELL',
                    shares=sell_shares,
                    price=price,
                    filled_price=trade['filled_price'],
                    amount=trade['amount'],
                    commission=trade['commission'],
                    stamp_duty=trade.get('stamp_duty', 0),
                    total_revenue=trade['total_revenue'],
                    trade_date=date
                )

                # 更新持仓
                self.portfolio[symbol]['shares'] = current_shares - sell_shares
                if self.portfolio[symbol]['shares'] == 0:
                    del self.portfolio[symbol]
                    self.repo.delete_position(self.account_name, symbol)

                logging.info(f"减仓 {symbol}: {sell_shares}股 @ ¥{price:.2f}")

    def _get_current_prices(self, symbols, date):
        """
        获取当前价格（多数据源策略）

        优先级：
        1. 实时行情（盘中有效）- RealtimeQuoteService（多源自动fallback）
        2. 数据库K线（盘后有效）
        3. 持仓成本价（兜底）
        """
        from application.services.realtime_quote_service import RealtimeQuoteService

        prices = {}

        # 数据源1: 实时行情（通过统一服务，自动多源fallback）
        quote_service = RealtimeQuoteService()
        for symbol in symbols:
            try:
                quote = quote_service.get_realtime_quote(symbol)
                if quote and quote.price > 0:
                    prices[symbol] = quote.price
                    logging.info(f"{symbol} 实时价格: {quote.price:.2f} (来源: {quote.source})")
            except Exception as e:
                logging.debug(f"{symbol} 实时行情获取失败: {e}")

        # 数据源2: 数据库K线（补齐缺失的）
        missing = [s for s in symbols if s not in prices]
        if missing:
            for symbol in missing:
                try:
                    latest = self.ds.kline.get_latest_daily_kline(symbol)
                    if latest is not None and not latest.is_empty():
                        price = float(latest['close'][0])
                        if price > 0:
                            prices[symbol] = price
                            logging.info(f"{symbol} 数据库价格: {price:.2f}")
                except Exception as e:
                    logging.debug(f"{symbol} 数据库K线获取失败: {e}")

        # 数据源3: 持仓成本价（最终兜底）
        for symbol in symbols:
            if symbol not in prices or prices[symbol] <= 0:
                if symbol in self.portfolio:
                    prices[symbol] = self.portfolio[symbol]['avg_price']
                    logging.warning(f"{symbol} 无法获取市场价格，使用成本价 {prices[symbol]:.2f}")
                else:
                    prices[symbol] = 0

        return prices

    def _execute_stop_loss(self, symbols, prices, date):
        """执行止损"""
        for symbol in symbols:
            if symbol not in self.portfolio:
                continue

            shares = self.portfolio[symbol]['shares']
            price = prices[symbol]

            # 模拟交易
            trade = self.broker.sell(symbol, shares, price)
            self.cash += trade['total_revenue']

            # 保存交易记录
            self.repo.add_trade(
                    account_name=self.account_name,
                symbol=symbol,
                action='SELL',
                shares=shares,
                price=price,
                filled_price=trade['filled_price'],
                amount=trade['amount'],
                commission=trade['commission'],
                stamp_duty=trade.get('stamp_duty', 0),
                total_revenue=trade['total_revenue'],
                trade_date=date
            )

            # 删除持仓
            del self.portfolio[symbol]
            self.repo.delete_position(self.account_name, symbol)

            logging.warning(f"止损卖出 {symbol}: {shares}股 @ ¥{price:.2f}")

    def _calculate_position_scale(self, current_return, drawdown):
        """计算仓位比例（旧方法，保留兼容性）"""
        # 检查止盈
        for level in self.config['strategy']['take_profit_levels']:
            if current_return >= level['threshold']:
                return level['position']

        # 检查止损
        for stop in self.config['strategy']['drawdown_stops']:
            if drawdown <= stop['threshold']:
                return stop['position']

        return 1.0

    def _execute_trades(self, top5, position_scale, date):
        """执行交易（旧方法，保留兼容性）"""
        target_symbols = set(top5['symbol'].tolist())
        target_weight = self.config['strategy']['position_weight'] * position_scale

        # 获取当前价格（使用实时数据接口）
        prices = {}
        for symbol in target_symbols | set(self.portfolio.keys()):
            try:
                latest = self.ds.kline.get_latest_daily_kline(symbol)
                if latest is not None and not latest.is_empty():
                    prices[symbol] = float(latest['close'][0])
                else:
                    prices[symbol] = self.portfolio.get(symbol, {}).get('avg_price', 0)
            except:
                if symbol in self.portfolio:
                    prices[symbol] = self.portfolio[symbol]['avg_price']

        # 卖出不在目标中的股票
        for symbol in list(self.portfolio.keys()):
            if symbol not in target_symbols:
                shares = self.portfolio[symbol]['shares']
                price = prices.get(symbol, self.portfolio[symbol]['avg_price'])

                # 模拟交易
                trade = self.broker.sell(symbol, shares, price)
                self.cash += trade['total_revenue']

                # 保存交易记录到数据库
                self.repo.add_trade(
                    account_name=self.account_name,
                    symbol=symbol,
                    action='SELL',
                    shares=shares,
                    price=price,
                    filled_price=trade['filled_price'],
                    amount=trade['amount'],
                    commission=trade['commission'],
                    stamp_duty=trade.get('stamp_duty', 0),
                    total_revenue=trade['total_revenue'],
                    trade_date=date
                )

                # 删除持仓
                del self.portfolio[symbol]
                self.repo.delete_position(self.account_name, symbol)

        # 计算总资产
        total_value = self.cash + sum(
            self.portfolio[s]['shares'] * prices.get(s, self.portfolio[s]['avg_price'])
            for s in self.portfolio
        )

        # 买入目标股票
        for symbol in target_symbols:
            target_value = total_value * target_weight
            price = prices.get(symbol, 0)

            if price <= 0:
                continue

            target_shares = int(target_value / price / 100) * 100  # 100股整数倍

            if target_shares == 0:
                continue

            # 如果已持有，调整仓位
            current_shares = self.portfolio.get(symbol, {}).get('shares', 0)
            delta_shares = target_shares - current_shares

            if delta_shares > 0:
                # 买入
                cost = delta_shares * price * (1 + self.config['trading']['commission_rate'])
                if cost <= self.cash:
                    trade = self.broker.buy(symbol, delta_shares, price)
                    self.cash -= trade['total_cost']

                    # 保存交易记录到数据库
                    self.repo.add_trade(
                    account_name=self.account_name,
                        symbol=symbol,
                        action='BUY',
                        shares=delta_shares,
                        price=price,
                        filled_price=trade['filled_price'],
                        amount=trade['amount'],
                        commission=trade['commission'],
                        total_cost=trade['total_cost'],
                        trade_date=date
                    )

                    if symbol in self.portfolio:
                        # 更新持仓成本
                        total_shares = self.portfolio[symbol]['shares'] + delta_shares
                        total_cost = (self.portfolio[symbol]['shares'] * self.portfolio[symbol]['avg_price'] +
                                     trade['total_cost'])
                        self.portfolio[symbol] = {
                            'shares': total_shares,
                            'avg_price': total_cost / total_shares
                        }
                    else:
                        self.portfolio[symbol] = {
                            'shares': delta_shares,
                            'avg_price': trade['total_cost'] / delta_shares
                        }

                    # 更新数据库持仓
                    self.repo.upsert_position(
                        account_name=self.account_name,
                        symbol=symbol,
                        shares=self.portfolio[symbol]['shares'],
                        avg_price=self.portfolio[symbol]['avg_price'],
                        current_price=price
                    )

            elif delta_shares < 0:
                # 卖出部分
                trade = self.broker.sell(symbol, abs(delta_shares), price)
                self.cash += trade['total_revenue']

                # 保存交易记录
                self.repo.add_trade(
                    account_name=self.account_name,
                    symbol=symbol,
                    action='SELL',
                    shares=abs(delta_shares),
                    price=price,
                    filled_price=trade['filled_price'],
                    amount=trade['amount'],
                    commission=trade['commission'],
                    stamp_duty=trade.get('stamp_duty', 0),
                    total_revenue=trade['total_revenue'],
                    trade_date=date
                )

                self.portfolio[symbol]['shares'] -= abs(delta_shares)

                # 更新数据库持仓
                self.repo.upsert_position(
                    symbol=symbol,
                    shares=self.portfolio[symbol]['shares'],
                    avg_price=self.portfolio[symbol]['avg_price'],
                    current_price=price
                )

        logging.info(f"\n交易完成:")
        logging.info(f"  现金余额: ¥{self.cash:,.2f}")
        logging.info(f"  持仓数量: {len(self.portfolio)}只")

    def generate_daily_report(self, date):
        """生成每日报告（保存到数据库）"""
        total_value = self._calculate_total_value_from_portfolio()
        initial_capital = self.config['initial_capital']

        # 获取昨日报告计算日收益
        previous_report = self.repo.get_latest_report()
        if previous_report:
            previous_value = float(previous_report['total_value'])
            daily_return = (total_value / previous_value - 1) if previous_value > 0 else 0
        else:
            daily_return = (total_value / initial_capital - 1)

        cumulative_return = (total_value / initial_capital - 1)
        drawdown = (total_value / self.peak_value - 1) if self.peak_value > 0 else 0

        # 计算持仓市值
        position_value = total_value - self.cash

        # 获取今日交易次数
        trade_count = self.repo.get_trade_count(account_name=self.account_name, start_date=date, end_date=date)

        # 保存到数据库
        self.repo.save_daily_report(
            report_date=date,
            cash=self.cash,
            position_value=position_value,
            total_value=total_value,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            peak_value=self.peak_value,
            drawdown=drawdown,
            position_count=len(self.portfolio),
            trade_count=trade_count
        )

        # 同时保存JSON文件（兼容）
        report_dir = Path(self.config['storage']['daily_report_file']).parent
        report_dir.mkdir(parents=True, exist_ok=True)

        report = {
            'date': date,
            'cash': self.cash,
            'position_value': position_value,
            'total_value': total_value,
            'daily_return': daily_return,
            'cumulative_return': cumulative_return,
            'drawdown': drawdown,
            'peak_value': self.peak_value,
            'position_count': len(self.portfolio),
            'trade_count': trade_count
        }

        report_file = report_dir / f"daily_{date}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logging.info(f"每日报告已保存到数据库和文件")


def main():
    """主函数"""
    print("V13策略模拟交易系统（数据库版）")
    print("="*60)

    # 初始化交易器
    trader = SimulationTrader()

    print("\n请选择操作:")
    print("1. 训练模型")
    print("2. 加载模型")
    print("3. 执行每日检查")
    print("4. 查看持仓（数据库）")
    print("5. 查看交易记录（数据库）")
    print("6. 查看每日报告（数据库）")
    print("7. 退出")

    choice = input("\n请输入选项 (1-7): ")

    if choice == '1':
        print("\n开始训练模型...")
        trader.train_model()
        print("模型训练完成!")

    elif choice == '2':
        print("\n加载模型...")
        trader.load_model()
        print("模型加载完成!")

    elif choice == '3':
        print("\n执行每日检查...")
        trader.run_daily_check()

    elif choice == '4':
        print("\n当前持仓（从数据库）:")
        account = trader.repo.get_account(trader.account_name)
        print(f"现金: ¥{float(account.cash_available or 0) + float(account.cash_frozen or 0):,.2f}")
        print(f"总资产: ¥{float(account.total_value or 0):,.2f}")
        print(f"累计收益: {float(account.cumulative_return or 0):.2%}")
        print(f"最大回撤: {float(account.max_drawdown or 0):.2%}")

        positions = trader.repo.get_all_positions(trader.account_name)
        print(f"\n持仓数量: {len(positions)}只")
        for pos in positions:
            print(f"  {pos.symbol}: {pos.shares_total}股 @ ¥{float(pos.avg_cost):.2f}")

    elif choice == '5':
        print("\n交易记录（从数据库）:")
        trades = trader.repo.get_trades(limit=20)
        if trades:
            for trade in trades:
                print(f"{trade['trade_time']} {trade['action']} {trade['symbol']} "
                      f"{trade['shares']}股 @ ¥{trade['filled_price']:.2f}")
            print(f"\n总手续费: ¥{trader.repo.get_total_commission():.2f}")
        else:
            print("暂无交易记录")

    elif choice == '6':
        print("\n每日报告（从数据库）:")
        reports = trader.repo.get_daily_reports(limit=10)
        if reports:
            for report in reports:
                print(f"{report['report_date']}: 总资产¥{report['total_value']:,.2f}, "
                      f"收益{report['cumulative_return']:.2%}, "
                      f"回撤{report['drawdown']:.2%}")
        else:
            print("暂无报告")

    elif choice == '7':
        print("\n退出系统")

    else:
        print("\n无效选项")


if __name__ == '__main__':
    main()
    def _send_rebalance_notification(self, current_date, top_stocks, weights, latest_factors, total_value):
        """发送调仓通知"""
        try:
            # 准备Top 8股票信息
            top_stocks_info = []
            for symbol in top_stocks[:8]:
                pred_return = latest_factors[latest_factors['symbol'] == symbol]['predicted_return'].iloc[0]
                weight = weights.get(symbol, 0)

                # 获取当前价格
                try:
                    df = self.ds.kline.get_stock_kline(
                        symbol=symbol,
                        start_date=current_date,
                        end_date=current_date
                    )
                    price = float(df.iloc[-1]['close']) if not df.empty else 0
                except:
                    price = 0

                # 判断是否买入/保留
                if symbol in self.portfolio:
                    note = f"(¥{price:.2f}，保留持仓)"
                else:
                    # 计算目标资金
                    target_value = total_value * weight * 0.7  # 假设仓位70%
                    can_buy = target_value >= price * 100 if price > 0 else False
                    if can_buy:
                        note = f"(¥{price:.2f}，买入)"
                    else:
                        note = f"(¥{price:.2f}，价格太高买不起)"

                top_stocks_info.append((symbol, pred_return, weight, note))

            # 收集买入/卖出交易（从最近的交易记录中获取）
            buy_trades = []
            sell_trades = []

            # 这里简化处理，实际应该从本次调仓的交易记录中提取
            for symbol, pos in self.portfolio.items():
                if symbol in top_stocks[:8]:
                    # 新买入或保留的
                    buy_trades.append((symbol, pos['shares'], pos['avg_price']))

            notification_data = {
                'date': current_date,
                'total_value': total_value,
                'cash': self.cash,
                'cumulative_return': (total_value / self.config['initial_capital'] - 1),
                'positions': len(self.portfolio),
                'top_stocks': top_stocks_info,
                'buy_trades': buy_trades,
                'sell_trades': sell_trades
            }

            self.feishu_notifier.send_rebalance_notification(notification_data)
            logging.info("飞书调仓通知已发送")

        except Exception as e:
            logging.error(f"发送飞书通知失败: {e}")
