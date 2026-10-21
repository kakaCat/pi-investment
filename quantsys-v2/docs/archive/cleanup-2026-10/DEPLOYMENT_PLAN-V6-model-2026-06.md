# V6模型部署实施方案

**模型版本**: V6 (因子筛选版)  
**部署时间**: 2026-06-20  
**负责人**: 量化团队  
**预计工期**: 2周

---

## 📋 部署清单

### 阶段1: 模型打包 (Day 1-2)

#### 1.1 模型序列化

**任务**: 保存训练好的V6模型

```python
# scripts/save_v6_model.py
import pickle
import json
from pathlib import Path
from datetime import datetime

# 保存模型
model_dir = Path('models/v6_production')
model_dir.mkdir(parents=True, exist_ok=True)

# 训练4个窗口的模型并保存
for window_id, (train_start, train_end, test_start, test_end) in enumerate(windows, 1):
    # ... 训练代码 ...
    
    # 保存模型
    model_file = model_dir / f'model_window_{window_id}.pkl'
    with open(model_file, 'wb') as f:
        pickle.dump(model, f)
    
    # 保存scaler
    scaler_file = model_dir / f'scaler_window_{window_id}.pkl'
    with open(scaler_file, 'wb') as f:
        pickle.dump(scaler, f)

# 保存有效因子列表
factors_file = model_dir / 'valid_factors.json'
with open(factors_file, 'w') as f:
    json.dump({'factors': valid_factors}, f, indent=2)

# 保存模型元数据
metadata = {
    'version': 'v6',
    'train_date': datetime.now().isoformat(),
    'ic_avg': 0.2500,
    'ir_avg': 0.48,
    'n_factors': len(valid_factors),
    'params': best_params
}
metadata_file = model_dir / 'metadata.json'
with open(metadata_file, 'w') as f:
    json.dump(metadata, f, indent=2)
```

**交付物**:
- `models/v6_production/model_window_*.pkl` (4个模型)
- `models/v6_production/scaler_window_*.pkl` (4个标准化器)
- `models/v6_production/valid_factors.json` (有效因子)
- `models/v6_production/metadata.json` (元数据)

---

#### 1.2 预测接口开发

**任务**: 实现预测API

```python
# application/services/ml_prediction_service.py

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta

class MLPredictionService:
    """V6模型预测服务"""
    
    def __init__(self, model_dir: str = 'models/v6_production'):
        self.model_dir = Path(model_dir)
        self.models = {}
        self.scalers = {}
        self.valid_factors = []
        self.metadata = {}
        
        self._load_models()
    
    def _load_models(self):
        """加载所有模型"""
        # 加载有效因子
        with open(self.model_dir / 'valid_factors.json') as f:
            self.valid_factors = json.load(f)['factors']
        
        # 加载元数据
        with open(self.model_dir / 'metadata.json') as f:
            self.metadata = json.load(f)
        
        # 加载4个窗口的模型
        for i in range(1, 5):
            model_file = self.model_dir / f'model_window_{i}.pkl'
            scaler_file = self.model_dir / f'scaler_window_{i}.pkl'
            
            with open(model_file, 'rb') as f:
                self.models[i] = pickle.load(f)
            
            with open(scaler_file, 'rb') as f:
                self.scalers[i] = pickle.load(f)
    
    def predict(self, symbols: List[str], date: str = None) -> pd.DataFrame:
        """
        预测股票的超额收益
        
        Args:
            symbols: 股票代码列表
            date: 预测日期（默认为当前日期）
        
        Returns:
            DataFrame: 包含symbol, prediction, rank列
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 1. 获取最新数据
        data_df = self._fetch_latest_data(symbols, date)
        
        # 2. 计算技术因子
        data_df = self._calculate_factors(data_df)
        
        # 3. 提取有效因子
        X = data_df[self.valid_factors].values
        
        # 4. 集成预测（4个模型平均）
        predictions = []
        for i in range(1, 5):
            X_scaled = self.scalers[i].transform(X)
            pred = self.models[i].predict(X_scaled)
            predictions.append(pred)
        
        # 平均预测
        avg_prediction = np.mean(predictions, axis=0)
        
        # 5. 构建结果
        result_df = pd.DataFrame({
            'symbol': data_df['symbol'],
            'date': date,
            'prediction': avg_prediction,
            'rank': pd.Series(avg_prediction).rank(ascending=False).astype(int)
        })
        
        # 按预测值排序
        result_df = result_df.sort_values('prediction', ascending=False)
        
        return result_df
    
    def get_top_stocks(self, symbols: List[str], top_n: int = 20) -> List[str]:
        """获取预测最佳的N只股票"""
        predictions = self.predict(symbols)
        return predictions.head(top_n)['symbol'].tolist()
    
    def _fetch_latest_data(self, symbols: List[str], date: str) -> pd.DataFrame:
        """获取最新数据（最近60天K线）"""
        from application.services.data_service import DataService
        
        ds = DataService()
        end_date = datetime.strptime(date, '%Y-%m-%d')
        start_date = end_date - timedelta(days=90)  # 多取一些保证60天数据
        
        # 获取K线数据
        kline_df = fetch_kline_data(symbols, 
                                     start_date.strftime('%Y-%m-%d'),
                                     end_date.strftime('%Y-%m-%d'))
        
        # 只保留最新日期的数据用于预测
        latest_date = kline_df['date'].max()
        return kline_df[kline_df['date'] <= latest_date]
    
    def _calculate_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术因子（复用V6代码）"""
        from train_ml_v6_optimized import calculate_technical_factors
        return calculate_technical_factors(df)
```

**交付物**:
- `application/services/ml_prediction_service.py`

---

### 阶段2: API集成 (Day 3-5)

#### 2.1 REST API端点

```python
# adapters/inbound/api/ml_prediction_api.py

from flask import Blueprint, request, jsonify
from application.services.ml_prediction_service import MLPredictionService

ml_bp = Blueprint('ml_prediction', __name__, url_prefix='/api/ml')

prediction_service = MLPredictionService()

@ml_bp.route('/predict', methods=['POST'])
def predict_stocks():
    """
    预测股票超额收益
    
    Request:
    {
        "symbols": ["600000", "000001", ...],
        "date": "2026-06-20"  # 可选
    }
    
    Response:
    {
        "date": "2026-06-20",
        "predictions": [
            {"symbol": "600000", "prediction": 0.015, "rank": 1},
            {"symbol": "000001", "prediction": 0.012, "rank": 2},
            ...
        ],
        "model_version": "v6",
        "model_ic": 0.2500
    }
    """
    data = request.json
    symbols = data.get('symbols', [])
    date = data.get('date', None)
    
    if not symbols:
        return jsonify({'error': 'symbols required'}), 400
    
    try:
        result_df = prediction_service.predict(symbols, date)
        
        return jsonify({
            'date': result_df['date'].iloc[0],
            'predictions': result_df.to_dict('records'),
            'model_version': 'v6',
            'model_ic': 0.2500,
            'model_ir': 0.48
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/top-stocks', methods=['POST'])
def get_top_stocks():
    """
    获取预测最佳的N只股票
    
    Request:
    {
        "symbols": ["600000", "000001", ...],
        "top_n": 20,
        "date": "2026-06-20"  # 可选
    }
    
    Response:
    {
        "date": "2026-06-20",
        "top_stocks": ["600000", "000001", ...],
        "count": 20
    }
    """
    data = request.json
    symbols = data.get('symbols', [])
    top_n = data.get('top_n', 20)
    date = data.get('date', None)
    
    try:
        result_df = prediction_service.predict(symbols, date)
        top_stocks = result_df.head(top_n)['symbol'].tolist()
        
        return jsonify({
            'date': result_df['date'].iloc[0],
            'top_stocks': top_stocks,
            'count': len(top_stocks)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/model-info', methods=['GET'])
def get_model_info():
    """获取模型信息"""
    return jsonify(prediction_service.metadata)
```

**测试**:
```bash
# 测试预测接口
curl -X POST http://localhost:5001/api/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["600000", "000001", "000002"],
    "date": "2026-06-20"
  }'

# 测试Top股票
curl -X POST http://localhost:5001/api/ml/top-stocks \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["600000", "000001", "000002"],
    "top_n": 10
  }'
```

**交付物**:
- `adapters/inbound/api/ml_prediction_api.py`
- API测试脚本

---

#### 2.2 CLI命令

```python
# adapters/inbound/cli/ml_commands.py

import click
from application.services.ml_prediction_service import MLPredictionService

@click.group()
def ml():
    """机器学习预测命令"""
    pass

@ml.command()
@click.option('--symbols', required=True, help='股票代码，逗号分隔')
@click.option('--date', default=None, help='预测日期')
@click.option('--top', default=20, help='显示前N只')
def predict(symbols, date, top):
    """预测股票超额收益"""
    service = MLPredictionService()
    
    symbol_list = symbols.split(',')
    result_df = service.predict(symbol_list, date)
    
    # 显示结果
    print(f"\n预测日期: {result_df['date'].iloc[0]}")
    print(f"模型版本: V6 (IC=0.25, IR=0.48)")
    print(f"\nTop {top} 股票:\n")
    print(result_df.head(top).to_string(index=False))

@ml.command()
def model_info():
    """显示模型信息"""
    service = MLPredictionService()
    
    print("\n模型信息:")
    print(f"  版本: {service.metadata['version']}")
    print(f"  训练日期: {service.metadata['train_date']}")
    print(f"  平均IC: {service.metadata['ic_avg']}")
    print(f"  平均IR: {service.metadata['ir_avg']}")
    print(f"  有效因子数: {service.metadata['n_factors']}")
    print(f"  因子列表: {', '.join(service.valid_factors[:5])}...")
```

**使用**:
```bash
# 预测
python cli/main.py ml predict --symbols "600000,000001,000002" --top 10

# 查看模型信息
python cli/main.py ml model-info
```

**交付物**:
- `adapters/inbound/cli/ml_commands.py`

---

### 阶段3: 定时任务 (Day 6-7)

#### 3.1 每日预测任务

```python
# infrastructure/jobs/daily_ml_prediction.py

from datetime import datetime
from application.services.ml_prediction_service import MLPredictionService
from application.services.data_service import DataService
import logging

logger = logging.getLogger(__name__)

def run_daily_prediction():
    """每日预测任务（每天收盘后运行）"""
    
    logger.info("开始每日ML预测...")
    
    # 1. 获取股票列表（沪深300）
    ds = DataService()
    symbols = get_etf300_stocks()
    
    logger.info(f"获取到 {len(symbols)} 只股票")
    
    # 2. 运行预测
    service = MLPredictionService()
    predictions = service.predict(symbols)
    
    # 3. 保存预测结果
    save_predictions(predictions)
    
    # 4. 生成报告
    generate_daily_report(predictions)
    
    logger.info("每日预测完成")
    
    return predictions


def save_predictions(predictions: pd.DataFrame):
    """保存预测结果到数据库"""
    from infrastructure.persistence.database.base_repository import BaseRepository
    
    BaseRepository.init_connection_pool()
    
    conn = BaseRepository.get_connection()
    cursor = conn.cursor()
    
    # 创建表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quant.ml_predictions (
            symbol TEXT NOT NULL,
            date DATE NOT NULL,
            prediction DOUBLE PRECISION,
            rank INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (symbol, date)
        )
    ''')
    
    # 插入预测
    for _, row in predictions.iterrows():
        cursor.execute('''
            INSERT INTO quant.ml_predictions (symbol, date, prediction, rank)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO UPDATE SET
                prediction = EXCLUDED.prediction,
                rank = EXCLUDED.rank,
                created_at = NOW()
        ''', (row['symbol'], row['date'], row['prediction'], row['rank']))
    
    conn.commit()
    cursor.close()
    BaseRepository.close_connection_pool()


def generate_daily_report(predictions: pd.DataFrame):
    """生成每日报告"""
    date = predictions['date'].iloc[0]
    
    report = f"""
# ML预测日报 - {date}

## Top 20 股票

| 排名 | 代码 | 预测收益 |
|------|------|----------|
"""
    
    for i, row in predictions.head(20).iterrows():
        report += f"| {row['rank']} | {row['symbol']} | {row['prediction']:.4f} |\n"
    
    report += f"""

## 统计信息

- 预测股票数: {len(predictions)}
- 预测均值: {predictions['prediction'].mean():.4f}
- 预测中位数: {predictions['prediction'].median():.4f}
- 预测标准差: {predictions['prediction'].std():.4f}

---
模型版本: V6 (IC=0.25, IR=0.48)
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # 保存报告
    report_file = Path(f'reports/daily/ml_prediction_{date}.md')
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding='utf-8')
```

**Cron配置**:
```python
# infrastructure/scheduler/cron_config.py

CRON_JOBS = [
    {
        'id': 'daily_ml_prediction',
        'schedule': '0 16 * * 1-5',  # 每个交易日下午4点
        'function': 'infrastructure.jobs.daily_ml_prediction:run_daily_prediction',
        'enabled': True
    }
]
```

**交付物**:
- `infrastructure/jobs/daily_ml_prediction.py`
- Cron配置

---

### 阶段4: 监控与告警 (Day 8-10)

#### 4.1 性能监控

```python
# infrastructure/monitoring/ml_monitor.py

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

class MLPerformanceMonitor:
    """ML模型性能监控"""
    
    def check_daily_performance(self, date: str):
        """检查某日的预测性能"""
        
        # 1. 获取5天前的预测
        pred_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=5)).strftime('%Y-%m-%d')
        predictions = self._get_predictions(pred_date)
        
        # 2. 获取实际收益
        actuals = self._get_actual_returns(pred_date, date)
        
        # 3. 计算IC
        ic = self._calculate_ic(predictions, actuals)
        
        # 4. 告警检查
        if ic < 0.10:  # 低于历史平均的40%
            self._send_alert(f"预测IC偏低: {ic:.4f} (日期: {pred_date})")
        
        # 5. 记录
        self._log_performance(pred_date, ic)
        
        return ic
    
    def _calculate_ic(self, predictions: pd.DataFrame, actuals: pd.DataFrame) -> float:
        """计算IC"""
        merged = predictions.merge(actuals, on='symbol')
        
        mask = ~(merged['prediction'].isna() | merged['actual_return'].isna())
        if mask.sum() < 10:
            return 0.0
        
        corr, _ = spearmanr(merged.loc[mask, 'prediction'], 
                           merged.loc[mask, 'actual_return'])
        
        return corr if not np.isnan(corr) else 0.0
    
    def _send_alert(self, message: str):
        """发送告警"""
        logger.warning(f"[ML Monitor] {message}")
        # TODO: 集成钉钉/企业微信告警
```

**交付物**:
- `infrastructure/monitoring/ml_monitor.py`

---

### 阶段5: 回测验证 (Day 11-14)

#### 5.1 完整历史回测

```python
# scripts/backtest_v6_model.py

def run_full_backtest():
    """完整历史回测"""
    
    # 回测期: 2025-06-20 ~ 2026-06-20
    backtest_results = []
    
    for date in trading_dates:
        # 1. 获取预测
        predictions = model.predict(symbols, date)
        
        # 2. 选择Top 20
        top_stocks = predictions.head(20)['symbol'].tolist()
        
        # 3. 计算5日后的收益
        returns = calculate_returns(top_stocks, date, hold_days=5)
        
        # 4. 计算基准收益（市场平均）
        benchmark = calculate_market_return(date, hold_days=5)
        
        # 5. 记录
        backtest_results.append({
            'date': date,
            'portfolio_return': returns.mean(),
            'benchmark_return': benchmark,
            'excess_return': returns.mean() - benchmark,
            'win_rate': (returns > 0).sum() / len(returns)
        })
    
    # 汇总
    results_df = pd.DataFrame(backtest_results)
    
    print(f"\n回测结果 (2025-06-20 ~ 2026-06-20):")
    print(f"  平均超额收益: {results_df['excess_return'].mean():.4f}")
    print(f"  累计超额收益: {results_df['excess_return'].sum():.4f}")
    print(f"  胜率: {(results_df['excess_return'] > 0).sum() / len(results_df):.2%}")
    print(f"  夏普比率: {results_df['excess_return'].mean() / results_df['excess_return'].std():.2f}")
    
    return results_df
```

**交付物**:
- 回测脚本
- 回测报告

---

## 📅 部署时间表

| 阶段 | 任务 | 工作日 | 负责人 |
|------|------|--------|--------|
| 1 | 模型打包 | Day 1-2 | ML工程师 |
| 2 | API集成 | Day 3-5 | 后端工程师 |
| 3 | 定时任务 | Day 6-7 | 后端工程师 |
| 4 | 监控告警 | Day 8-10 | DevOps |
| 5 | 回测验证 | Day 11-14 | 量化研究员 |

**总工期**: 2周（10个工作日）

---

## ✅ 验收标准

### 功能验收

- [ ] V6模型成功加载
- [ ] REST API正常响应
- [ ] CLI命令正常运行
- [ ] 定时任务按时执行
- [ ] 预测结果正确保存
- [ ] 监控告警正常工作

### 性能验收

- [ ] API响应时间 < 3秒
- [ ] 每日预测任务 < 5分钟
- [ ] 预测准确率与回测一致

### 文档验收

- [ ] API文档完整
- [ ] 部署文档清晰
- [ ] 运维手册完善

---

## 🚨 风险与应对

### 风险1: 模型加载失败

**应对**: 
- 验证pickle版本兼容性
- 准备模型重训练脚本

### 风险2: 实时数据延迟

**应对**:
- 设置数据缓存
- 监控数据更新时间

### 风险3: 预测性能下降

**应对**:
- 每日IC监控
- 准备模型重训练流程

---

## 📞 支持联系

**技术支持**: 量化团队  
**运维支持**: DevOps团队  
**紧急联系**: [待填写]

---

**文档版本**: 1.0  
**创建日期**: 2026-06-20  
**最后更新**: 2026-06-20
