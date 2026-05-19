"""
量化系统 API 服务

提供RESTful API供前端调用
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.factors.calculator import FactorCalculator
from quantsys.data.db import Database
from scripts.analyze_feature_importance import analyze_feature_importance, load_model, get_feature_names
from quantsys.ml.features.feature_engineering import FeatureEngineer

app = Flask(__name__)
CORS(app)  # 允许跨域

# 全局变量
db = None
model = None
factor_calculator = None
feature_engineer = None


def init_services():
    """初始化服务"""
    global db, model, factor_calculator, feature_engineer

    # 存储数据库路径，但不创建连接（避免线程问题）
    # 使用项目根目录下的 .pi-invest/stock-db/stocks.db（包含完整股票+ K线数据）
    # 优先级: 环境变量 > 项目根目录 > home目录
    global db_path
    _project_root = Path(__file__).parent.parent.parent  # quant/api/ → quant/ → project_root/
    _project_db = _project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
    _home_db = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'
    db_path = _project_db if _project_db.exists() else _home_db

    # 尝试多个模型路径（优先加载新模型）
    model_paths = [
        Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_latest.pkl',
        Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_model.pkl',
        Path(__file__).parent.parent.parent / '.pi-invest' / 'quant' / 'models' / 'signal_confidence.pkl',
    ]

    for model_path in model_paths:
        if model_path.exists():
            try:
                model = load_model(str(model_path))
                print(f"✅ Model loaded from: {model_path}")
                break
            except Exception as e:
                print(f"⚠️ Failed to load model from {model_path}: {e}")

    if model is None:
        print("⚠️ No model loaded - ML features will be unavailable")

    factor_calculator = FactorCalculator()
    feature_engineer = FeatureEngineer()


def _ensure_schema(conn):
    """确保数据库包含必要的表（增量迁移，不破坏已有数据）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS factor_values (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            factor_value REAL,
            PRIMARY KEY (symbol, date, factor_name)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_values_symbol
        ON factor_values(symbol)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_values_date
        ON factor_values(date)
    """)
    conn.commit()


def get_db():
    """获取线程安全的数据库连接"""
    import sqlite3
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    db_connected = False
    try:
        conn = get_db()
        conn.close()
        db_connected = True
    except:
        pass

    return jsonify({
        'status': 'ok',
        'model_loaded': model is not None,
        'db_connected': db_connected
    })


@app.route('/api/feature-importance', methods=['GET'])
def get_feature_importance():
    """获取因子重要性"""
    try:
        if model is None:
            return jsonify({'error': '模型未加载'}), 500

        # 获取模型路径（优先使用新模型）
        model_path = None
        for path in [
            Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_latest.pkl',
            Path(__file__).parent.parent.parent / '.pi-invest' / 'quant' / 'models' / 'signal_confidence.pkl',
        ]:
            if path.exists():
                model_path = str(path)
                break

        df = analyze_feature_importance(model, model_path)

        # 转换为前端期望的格式（小写字段名）
        features = []
        for _, row in df.iterrows():
            features.append({
                'feature': row['Feature'],
                'importance': float(row['Importance']),
                'percentage': float(row['Percentage']) if row['Percentage'] is not None else 0.0,
                'cumulative': float(row['Cumulative']) if row['Cumulative'] is not None else 0.0
            })

        return jsonify({
            'features': features,
            'total_features': len(df),
            'top_20_percent_count': len(df[df['Cumulative'] <= 80]) if 'Cumulative' in df.columns else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/<symbol>/factors', methods=['GET'])
def get_stock_factors(symbol):
    """获取股票因子分析"""
    try:
        date = request.args.get('date')

        if model is None:
            return jsonify({'error': '模型未加载'}), 500

        conn = get_db()

        # 获取最新日期
        if date is None:
            cursor = conn.execute(
                "SELECT MAX(date) FROM factor_values WHERE symbol = ?",
                (symbol,)
            )
            date = cursor.fetchone()[0]
            if not date:
                conn.close()
                return jsonify({'error': f'未找到股票 {symbol} 的数据'}), 404

        # 获取因子和价格
        cursor = conn.execute("""
            SELECT factor_name, factor_value
            FROM factor_values
            WHERE symbol = ? AND date = ?
        """, (symbol, date))

        factors = {}
        for row in cursor.fetchall():
            factors[row[0]] = row[1]

        cursor = conn.execute("""
            SELECT open, high, low, close, volume, amount, turnover_rate
            FROM daily_klines
            WHERE symbol = ? AND date = ?
        """, (symbol, date))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'error': '未找到价格数据'}), 404

        # 构建特征字典（与训练时一致）
        feature_dict = {
            'open': row[0],
            'high': row[1],
            'low': row[2],
            'close': row[3],
            'volume': row[4],
            'amount': row[5],
            'turnover_rate': row[6]
        }

        # 添加因子数据
        feature_dict.update(factors)

        # 从训练报告读取特征顺序
        import json
        report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report_latest.json'
        with open(report_path) as f:
            report = json.load(f)
            feature_names = report['feature_names']

        # 按训练时的顺序构建特征数组（缺失的特征用 0 填充）
        features = []
        missing_features = []
        for name in feature_names:
            value = feature_dict.get(name, None)
            if value is None:
                missing_features.append(name)
                features.append(0.0)
            else:
                features.append(float(value))

        # 预测
        X = np.array(features).reshape(1, -1)
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(X)[0]
            up_prob = float(proba[1])
        else:
            up_prob = float(model.predict(X)[0])

        # 计算因子贡献
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            contributions = np.array(features) * importances

            key_factors = []
            for i, name in enumerate(feature_names):
                key_factors.append({
                    'name': name,
                    'value': float(features[i]),
                    'importance': float(importances[i]),
                    'contribution': float(contributions[i])
                })

            # 按贡献排序
            key_factors.sort(key=lambda x: abs(x['contribution']), reverse=True)
        else:
            key_factors = []

        return jsonify({
            'symbol': symbol,
            'date': date,
            'price': feature_dict['close'],
            'prediction': {
                'up_probability': up_prob,
                'direction': 'UP' if up_prob > 0.5 else 'DOWN',
                'confidence': abs(up_prob - 0.5) * 2
            },
            'key_factors': key_factors[:10]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/compare', methods=['POST'])
def compare_stocks():
    """对比多只股票"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        date = data.get('date')

        if not symbols:
            return jsonify({'error': '请提供股票代码'}), 400

        if len(symbols) > 5:
            return jsonify({'error': '最多对比5只股票'}), 400

        results = []
        for symbol in symbols:
            try:
                # 复用 get_stock_factors 的逻辑
                with app.test_request_context(f'/api/stock/{symbol}/factors', query_string={'date': date}):
                    response = get_stock_factors(symbol)
                    if response[1] == 200:  # 成功
                        results.append(response[0].get_json())
            except Exception as e:
                print(f"Failed to analyze {symbol}: {e}")
                continue

        # 按上涨概率排序
        results.sort(key=lambda x: x['prediction']['up_probability'], reverse=True)

        return jsonify({
            'comparisons': results,
            'count': len(results)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/signals', methods=['GET'])
def get_signals():
    """获取交易信号"""
    try:
        date = request.args.get('date')

        # 读取信号文件
        signals_path = Path(__file__).parent.parent / '.pi-invest' / 'signals.json'

        if not signals_path.exists():
            return jsonify({'signals': []})

        import json
        with open(signals_path, 'r') as f:
            data = json.load(f)
            # signals.json 结构: {generated_at, date, summary, signals: [...]}
            # 必须提取 signals 数组，不能直接返回整个文件对象
            signals = data.get('signals', [])
            if not isinstance(signals, list):
                signals = []

        # 过滤日期/信号类型/置信度
        if date:
            signals = [s for s in signals if s.get('date') == date]
        signal_type = request.args.get('signal_type')
        if signal_type:
            signals = [s for s in signals if s.get('signal') == signal_type]
        min_confidence = request.args.get('min_confidence', type=float)
        if min_confidence:
            signals = [s for s in signals if s.get('confidence', 0) >= min_confidence]

        return jsonify({
            'signals': signals,
            'count': len(signals),
            'date': data.get('date', '')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/<symbol>/klines', methods=['GET'])
def get_stock_klines(symbol):
    """获取K线数据（兼容 quant_api.py 格式）"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', type=int, default=100)

        klines = _get_klines_raw(symbol, limit=limit, start_date=start_date, end_date=end_date)

        if not klines:
            return jsonify({'error': f'No kline data for {symbol}'}), 404

        return jsonify({
            'symbol': symbol,
            'count': len(klines),
            'klines': klines
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _get_klines_raw(symbol, limit=100, start_date=None, end_date=None):
    """内部辅助：获取K线原始数据"""
    conn = get_db()
    query = """
        SELECT date, open, high, low, close, volume, amount
        FROM daily_klines
        WHERE symbol = ?
    """
    params = [symbol]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date DESC"
    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    klines = []
    for row in rows:
        klines.append({
            'date': row[0],
            'open': float(row[1]) if row[1] is not None else 0.0,
            'high': float(row[2]) if row[2] is not None else 0.0,
            'low': float(row[3]) if row[3] is not None else 0.0,
            'close': float(row[4]) if row[4] is not None else 0.0,
            'volume': float(row[5]) if row[5] is not None else 0.0,
            'amount': float(row[6]) if row[6] is not None else 0.0
        })
    klines.sort(key=lambda x: x['date'])
    return klines


@app.route('/api/stock/<symbol>/technical', methods=['GET'])
def get_technical_indicators(symbol):
    """计算技术指标（兼容 quant_api.py 格式）"""
    try:
        indicators_param = request.args.get('indicators')
        indicators_list = indicators_param.split(',') if indicators_param else None

        klines = _get_klines_raw(symbol, limit=100)

        if not klines:
            return jsonify({'error': f'No kline data for {symbol}'}), 404

        if len(klines) < 20:
            return jsonify({'error': f'Insufficient data for {symbol} (need 20+ days, got {len(klines)})'}), 400

        # 转换为 pandas DataFrame
        import pandas as pd
        df = pd.DataFrame(klines)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        result_indicators = {}

        # RSI
        if not indicators_list or 'RSI' in indicators_list:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            result_indicators['RSI'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

        # MA5, MA10, MA20, MA60
        for period in [5, 10, 20, 60]:
            key = f'MA{period}'
            if not indicators_list or key in indicators_list:
                ma = df['close'].rolling(window=period).mean()
                result_indicators[key] = float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None

        # MACD
        if not indicators_list or 'MACD' in indicators_list or 'MACD_DIF' in indicators_list:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd_dif = exp1 - exp2
            macd_dea = macd_dif.ewm(span=9, adjust=False).mean()
            macd_histogram = macd_dif - macd_dea

            result_indicators['MACD_DIF'] = float(macd_dif.iloc[-1]) if not pd.isna(macd_dif.iloc[-1]) else None
            result_indicators['MACD_DEA'] = float(macd_dea.iloc[-1]) if not pd.isna(macd_dea.iloc[-1]) else None
            result_indicators['MACD'] = float(macd_histogram.iloc[-1]) if not pd.isna(macd_histogram.iloc[-1]) else None

        # 计算当前价格
        current_price = float(df['close'].iloc[-1])

        return jsonify({
            'symbol': symbol,
            'date': klines[-1]['date'],
            'price': current_price,
            'indicators': result_indicators
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/list', methods=['GET'])
def get_stock_list():
    """获取股票列表（兼容 quant_api.py 格式）"""
    try:
        market = request.args.get('market')
        has_data = request.args.get('has_data', type=bool, default=False)

        conn = get_db()

        if has_data:
            query = """
                SELECT DISTINCT s.symbol, s.name, s.market
                FROM stocks s
                INNER JOIN daily_klines k ON s.symbol = k.symbol
            """
            params = []
            if market:
                query += " WHERE s.market = ?"
                params.append(market)
            query += " ORDER BY s.symbol"
        else:
            query = "SELECT symbol, name, market FROM stocks"
            params = []
            if market:
                query += " WHERE market = ?"
                params.append(market)
            query += " ORDER BY symbol"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2]
            })

        return jsonify({
            'count': len(stocks),
            'stocks': stocks
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/report/daily', methods=['GET'])
def get_daily_report():
    """获取每日报告（兼容 quant_api.py 格式）"""
    try:
        date = request.args.get('date')

        # 读取报告文件
        reports_dir = Path(__file__).parent.parent.parent / '.pi-invest' / 'reports'

        if date:
            report_file = Path(__file__).parent.parent.parent / '.pi-invest' / f'daily_report_{date}.json'
        else:
            report_file = Path(__file__).parent.parent.parent / '.pi-invest' / 'daily_report.json'

        if not report_file.exists():
            # 尝试从 .pi-invest/reports/ 查找
            if date:
                alt_file = reports_dir / f'{date}-review.md'
            else:
                # 找最新的报告
                md_files = sorted(reports_dir.glob('*-review.md'), reverse=True)
                alt_file = md_files[0] if md_files else None

            if alt_file and alt_file.exists():
                with open(alt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({
                    'date': alt_file.stem.replace('-review', ''),
                    'report': {'content': content, 'format': 'markdown'}
                })

            return jsonify({'error': 'Daily report not found'}), 404

        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)

        return jsonify(report)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/<symbol>/ml-predict', methods=['GET'])
def get_ml_prediction(symbol):
    """获取ML预测（供 predict_stock_ml 工具使用）"""
    try:
        if model is None:
            return jsonify({'error': '模型未加载'}), 500

        conn = get_db()

        # 获取最新日期
        cursor = conn.execute(
            "SELECT MAX(date) FROM factor_values WHERE symbol = ?",
            (symbol,)
        )
        row = cursor.fetchone()
        date = row[0] if row else None
        if not date:
            conn.close()
            return jsonify({'error': f'未找到股票 {symbol} 的数据'}), 404

        # 获取因子值
        cursor = conn.execute("""
            SELECT factor_name, factor_value
            FROM factor_values
            WHERE symbol = ? AND date = ?
        """, (symbol, date))
        factors = {row[0]: row[1] for row in cursor.fetchall()}

        # 获取价格数据（优先用因子日期，fallback 到最近有K线的日期）
        cursor = conn.execute("""
            SELECT open, high, low, close, volume, amount, turnover_rate
            FROM daily_klines
            WHERE symbol = ? AND date = ?
        """, (symbol, date))
        row = cursor.fetchone()
        
        # 如果因子日期没有K线，fallback到最近有K线的日期
        if not row:
            cursor = conn.execute("""
                SELECT open, high, low, close, volume, amount, turnover_rate
                FROM daily_klines
                WHERE symbol = ?
                ORDER BY date DESC LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
        
        conn.close()

        if not row:
            return jsonify({'error': '未找到价格数据'}), 404

        feature_dict = {
            'open': row[0], 'high': row[1], 'low': row[2],
            'close': row[3], 'volume': row[4], 'amount': row[5],
            'turnover_rate': row[6]
        }
        feature_dict.update(factors)

        # 从训练报告读取特征顺序
        import json
        report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report_latest.json'
        if not report_path.exists():
            # Try fallback path
            report_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'training_report.json'
        if not report_path.exists():
            return jsonify({'error': '训练报告文件不存在，请先训练模型'}), 500

        with open(report_path) as f:
            report = json.load(f)
            feature_names = report['feature_names']

        # 按训练顺序构建特征数组
        features = []
        for name in feature_names:
            value = feature_dict.get(name, None)
            features.append(float(value) if value is not None else 0.0)

        # ML预测
        X = np.array(features).reshape(1, -1)
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(X)[0]
            up_prob = float(proba[1])
        else:
            up_prob = float(model.predict(X)[0])

        # 因子贡献
        key_factors = []
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            contributions = np.array(features) * importances
            for i, name in enumerate(feature_names):
                key_factors.append({
                    'name': name,
                    'value': float(features[i]),
                    'importance': float(importances[i]),
                    'contribution': float(contributions[i])
                })
            key_factors.sort(key=lambda x: abs(x['contribution']), reverse=True)

        return jsonify({
            'symbol': symbol,
            'date': date,
            'price': feature_dict['close'],
            'prediction': {
                'up_probability': up_prob,
                'direction': 'UP' if up_prob > 0.5 else 'DOWN',
                'confidence': abs(up_prob - 0.5) * 2
            },
            'key_factors': key_factors[:5]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest/results', methods=['GET'])
def get_backtest_results():
    """获取回测结果"""
    try:
        import json
        import glob

        symbol = request.args.get('symbol')
        date = request.args.get('date')

        backtest_dir = Path(__file__).parent.parent / '.pi-invest'

        if symbol and date:
            # 获取特定股票特定日期的回测结果
            report_file = backtest_dir / f'backtest_report_{symbol}_{date}.json'
            if not report_file.exists():
                return jsonify({'error': f'未找到回测报告: {symbol} {date}'}), 404

            with open(report_file, 'r') as f:
                report = json.load(f)
            return jsonify(report)

        elif symbol:
            # 获取特定股票的所有回测结果
            pattern = str(backtest_dir / f'backtest_report_{symbol}_*.json')
            files = glob.glob(pattern)

            reports = []
            for file in sorted(files, reverse=True):
                with open(file, 'r') as f:
                    reports.append(json.load(f))

            return jsonify({
                'symbol': symbol,
                'count': len(reports),
                'reports': reports
            })

        else:
            # 获取所有回测结果的汇总
            pattern = str(backtest_dir / 'backtest_report_*_*.json')
            files = glob.glob(pattern)

            if not files:
                # 没有回测报告，返回空列表
                return jsonify({
                    'count': 0,
                    'summary': []
                })

            summary = []
            for file in files:
                with open(file, 'r') as f:
                    report = json.load(f)
                    # 提取关键信息
                    best_strategy = max(report['results'], key=lambda x: x.get('total_return', -999))
                    summary.append({
                        'symbol': report['symbol'],
                        'date': report['report_date'],
                        'best_strategy': best_strategy['strategy_name'],
                        'best_return': best_strategy['total_return'],
                        'sharpe_ratio': best_strategy['sharpe_ratio'],
                        'max_drawdown': best_strategy['max_drawdown'],
                        'win_rate': best_strategy['win_rate']
                    })

            # 按收益率排序
            summary.sort(key=lambda x: x['best_return'], reverse=True)

            return jsonify({
                'count': len(summary),
                'summary': summary
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/history', methods=['GET'])
def get_training_history():
    """获取训练历史"""
    try:
        models_dir = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models'

        import glob
        import json
        pattern = str(models_dir / 'training_report_*.json')
        files = glob.glob(pattern)

        # 排除 latest 文件
        files = [f for f in files if 'latest' not in f]

        history = []
        for file in sorted(files, reverse=True):
            with open(file, 'r') as f:
                report = json.load(f)
                history.append({
                    'timestamp': report['timestamp'],
                    'model_type': report['model_type'],
                    'n_features': report['data']['n_features'],
                    'total_samples': report['data']['total_samples'],
                    'cv_accuracy': report['cv_results']['mean_scores']['accuracy'],
                    'cv_auc': report['cv_results']['mean_scores']['auc'],
                    'test_accuracy': report['test_metrics']['accuracy'],
                    'test_auc': report['test_metrics']['auc'],
                    'class_balance': report['data']['class_balance']
                })

        return jsonify({
            'count': len(history),
            'history': history
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/data-status', methods=['GET'])
def get_stocks_data_status():
    """获取所有股票的数据状态"""
    try:
        conn = get_db()

        # 获取所有股票及其数据统计
        query = """
        SELECT
            s.symbol,
            s.name,
            s.market,
            COUNT(DISTINCT k.date) as kline_days,
            MIN(k.date) as earliest_date,
            MAX(k.date) as latest_date,
            COUNT(DISTINCT f.date) as factor_days,
            COUNT(DISTINCT f.factor_name) as factor_count
        FROM stocks s
        LEFT JOIN daily_klines k ON s.symbol = k.symbol
        LEFT JOIN factor_values f ON s.symbol = f.symbol
        GROUP BY s.symbol, s.name, s.market
        ORDER BY s.symbol
        """

        cursor = conn.execute(query)
        rows = cursor.fetchall()
        conn.close()

        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2],
                'kline_days': row[3],
                'earliest_date': row[4],
                'latest_date': row[5],
                'factor_days': row[6],
                'factor_count': row[7],
                'data_complete': row[3] > 0 and row[6] > 0 and row[7] >= 30
            })

        # 统计
        total_stocks = len(stocks)
        complete_stocks = sum(1 for s in stocks if s['data_complete'])

        return jsonify({
            'total_stocks': total_stocks,
            'complete_stocks': complete_stocks,
            'incomplete_stocks': total_stocks - complete_stocks,
            'stocks': stocks
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('🚀 启动量化系统API服务...')
    init_services()
    print('✅ 服务初始化完成')
    print('📡 API地址: http://localhost:5001')
    print('📊 健康检查: http://localhost:5001/api/health')
    print('📈 可用端点:')
    print('   GET /api/health')
    print('   GET /api/feature-importance')
    print('   GET /api/stock/<symbol>/factors')
    print('   GET /api/stock/<symbol>/klines')
    print('   GET /api/stock/<symbol>/technical')
    print('   GET /api/stock/<symbol>/ml-predict')
    print('   POST /api/stocks/compare')
    print('   GET /api/stocks/list')
    print('   GET /api/stocks/data-status')
    print('   GET /api/signals')
    print('   GET /api/report/daily')
    print('   GET /api/backtest/results')
    print('   GET /api/training/history')
    app.run(host='0.0.0.0', port=5001, debug=True)
