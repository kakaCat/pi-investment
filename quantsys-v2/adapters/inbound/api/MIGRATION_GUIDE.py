"""
API 重构迁移指南

本指南说明如何将旧的 API 路由迁移到新的装饰器模式。
"""

# ==================== 迁移步骤 ====================

"""
步骤1: 导入新模块
"""
# 在 api/server.py 顶部添加：
from .decorators import validate_params, handle_errors, paginate
from .validators import (
    validate_stock_symbol, validate_date, validate_signal_type,
    ValidationError
)
from .response_builder import (
    success_response, error_response, list_response,
    paginated_response, created_response, not_found_response
)
from .error_handlers import register_error_handlers

# 注册全局错误处理器
register_error_handlers(app)


"""
步骤2: 识别重构模式
"""

# 模式1: 简单GET请求 + 参数验证
# 旧代码：
@app.route('/api/stocks/data-status', methods=['GET'])
def data_status():
    symbol = request.args.get('symbol', '000001.SZ')
    try:
        result = ds.check_data_integrity(symbol)
        return jsonify(sanitize_for_json(result))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新代码：
@app.route('/api/stocks/data-status', methods=['GET'])
@handle_errors
@validate_params({
    'symbol': {'type': str, 'default': '000001.SZ', 'validator': validate_stock_symbol, 'source': 'args'}
})
def data_status(symbol):
    result = ds.check_data_integrity(symbol)
    return success_response(**result)


# 模式2: POST请求 + JSON参数验证
# 旧代码：
@app.route('/api/stocks/resolve', methods=['POST'])
def resolve_stock():
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'error': '股票代码不能为空'}), 400

    try:
        stock = ds.stock.get_by_symbol(code)
        if not stock:
            return jsonify({'found': False, 'symbol': code}), 404

        return jsonify({
            'found': True,
            'symbol': stock['symbol'],
            'name': stock['name'],
            'market': stock.get('market', ''),
            'industry': stock.get('industry', '')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新代码：
@app.route('/api/stocks/resolve', methods=['POST'])
@handle_errors
@validate_params({
    'code': {'type': str, 'required': True, 'validator': validate_stock_symbol, 'source': 'json'}
})
def resolve_stock(code):
    stock = ds.stock.get_by_symbol(code)
    if not stock:
        return not_found_response('股票', code)

    return success_response(
        found=True,
        symbol=stock['symbol'],
        name=stock['name'],
        market=stock.get('market', ''),
        industry=stock.get('industry', '')
    )


# 模式3: 分页查询
# 旧代码：
@app.route('/api/stocks/search', methods=['GET'])
def search_stocks():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': '搜索关键词不能为空'}), 400

    page = max(1, request.args.get('page', 1, type=int))
    page_size = max(1, min(request.args.get('pageSize', 20, type=int), 100))
    offset = (page - 1) * page_size

    try:
        results = ds.stock.search(q, limit=page_size + offset)
        total = len(results)
        stocks = results[offset:offset + page_size]

        return jsonify({
            'query': q,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'stocks': [...]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新代码：
@app.route('/api/stocks/search', methods=['GET'])
@handle_errors
@paginate(default_page_size=20, max_page_size=100)
@validate_params({
    'q': {'type': str, 'required': True, 'min_length': 1, 'source': 'args'}
})
def search_stocks(q, page, page_size, offset):
    results = ds.stock.search(q, limit=page_size + offset)
    total = len(results)
    stocks = results[offset:offset + page_size]

    return paginated_response(
        items=[...],
        total=total,
        page=page,
        page_size=page_size,
        query=q
    )


# 模式4: 路径参数
# 旧代码：
@app.route('/api/stock/<symbol>/klines', methods=['GET'])
def get_stock_klines(symbol):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)

        # ... 处理逻辑

        return jsonify({
            'symbol': symbol,
            'count': len(klines),
            'klines': sanitize_for_json(klines[-limit:])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新代码：
@app.route('/api/stock/<symbol>/klines', methods=['GET'])
@handle_errors
@validate_params({
    'symbol': {'type': str, 'required': True, 'validator': validate_stock_symbol, 'source': 'path'},
    'start_date': {'type': str, 'validator': validate_date, 'source': 'args'},
    'end_date': {'type': str, 'validator': validate_date, 'source': 'args'},
    'limit': {'type': int, 'default': 100, 'min': 1, 'max': 1000, 'source': 'args'}
})
def get_stock_klines(symbol, start_date, end_date, limit):
    # 处理默认日期
    if not start_date or not end_date:
        end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        start_date = start_date or (datetime.now() - timedelta(days=limit)).strftime('%Y-%m-%d')

    klines = ds.kline.get_daily_klines(symbol, start_date, end_date, fields=[...])

    if not klines:
        return not_found_response('K线数据', symbol)

    return success_response(
        symbol=symbol,
        count=len(klines),
        klines=klines[-limit:]
    )


# 模式5: 创建资源 (POST + 201)
# 旧代码：
@app.route('/api/stocks/add', methods=['POST'])
def add_stock():
    data = request.get_json() or {}
    try:
        ds.stock.save(data)
        return jsonify({'success': True, 'symbol': data.get('symbol')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新代码：
@app.route('/api/stocks/add', methods=['POST'])
@handle_errors
@validate_params({
    'symbol': {'type': str, 'required': True, 'validator': validate_stock_symbol, 'source': 'json'},
    'name': {'type': str, 'required': True, 'source': 'json'},
    'market': {'type': str, 'validator': validate_market, 'source': 'json'}
})
def add_stock(symbol, name, market):
    data = {'symbol': symbol, 'name': name, 'market': market}
    ds.stock.save(data)
    return created_response(
        resource_id=symbol,
        message='股票添加成功'
    )


# 模式6: 列表查询
# 旧代码：
@app.route('/api/signals', methods=['GET'])
def get_signals():
    try:
        date = request.args.get('date')
        signal_type = request.args.get('signal_type')
        min_confidence = request.args.get('min_confidence', 0.0, type=float)

        if date:
            signals = ds.signal.get_signals_by_date(date, signal_type=signal_type)
        else:
            signals = ds.signal.get_latest_signals(limit=100)

        if min_confidence > 0:
            signals = [s for s in signals if (s.get('confidence') or 0) >= min_confidence]

        return jsonify({
            'signals': sanitize_for_json(signals),
            'count': len(signals),
            'date': date or '',
            'source': 'database'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新代码：
@app.route('/api/signals', methods=['GET'])
@handle_errors
@validate_params({
    'date': {'type': str, 'validator': validate_date, 'source': 'args'},
    'signal_type': {'type': str, 'validator': validate_signal_type, 'source': 'args'},
    'min_confidence': {'type': float, 'default': 0.0, 'min': 0.0, 'max': 1.0, 'source': 'args'},
    'limit': {'type': int, 'default': 100, 'min': 1, 'max': 500, 'source': 'args'}
})
def get_signals(date, signal_type, min_confidence, limit):
    if date:
        signals = ds.signal.get_signals_by_date(date, signal_type=signal_type)
    else:
        signals = ds.signal.get_latest_signals(limit=limit)

    if min_confidence > 0:
        signals = [s for s in signals if (s.get('confidence') or 0) >= min_confidence]

    return list_response(
        items=signals,
        item_name='signals',
        date=date or '',
        source='database'
    )


"""
步骤3: 迁移优先级
"""

# 高优先级（高频使用）：
# 1. /api/stocks/search - 股票搜索
# 2. /api/stock/<symbol>/klines - K线查询
# 3. /api/stock/<symbol>/factors - 因子查询
# 4. /api/signals - 信号查询
# 5. /api/stocks/compare - 股票对比

# 中优先级（常用）：
# 6. /api/stocks/list - 股票列表
# 7. /api/stocks/resolve - 股票解析
# 8. /api/backtest/results - 回测结果
# 9. /api/risk/check - 风险检查
# 10. /api/data/update - 数据更新

# 低优先级（管理功能）：
# 11. /api/executions/* - 执行记录管理
# 12. /api/compute/* - 计算任务
# 13. /api/performance/* - 性能统计


"""
步骤4: 测试迁移后的路由
"""

# 运行测试：
# pytest tests/test_api_decorators.py -v
# pytest tests/test_api_validators.py -v

# 手动测试：
# curl http://localhost:5000/api/stocks/search?q=平安
# curl -X POST http://localhost:5000/api/stocks/resolve -H "Content-Type: application/json" -d '{"code":"000001.SZ"}'


"""
步骤5: 验证响应格式
"""

# 成功响应格式：
{
    "success": true,
    "data": {...},
    "message": "操作成功"  # 可选
}

# 错误响应格式：
{
    "success": false,
    "error": "错误消息",
    "error_code": "VALIDATION_ERROR",  # 可选
    "details": {...}  # 可选
}

# 分页响应格式：
{
    "success": true,
    "data": [...],
    "pagination": {
        "total": 100,
        "page": 1,
        "page_size": 20,
        "total_pages": 5
    }
}

# 列表响应格式：
{
    "success": true,
    "signals": [...],
    "count": 10
}


"""
步骤6: 常见问题
"""

# Q1: 如何处理可选参数？
# A: 使用 'default' 字段
@validate_params({
    'limit': {'type': int, 'default': 100, 'source': 'args'}
})

# Q2: 如何验证多个参数的组合？
# A: 在函数内部进行业务逻辑验证
def my_route(start_date, end_date):
    if start_date > end_date:
        raise ValidationError("开始日期不能晚于结束日期")

# Q3: 如何处理复杂的JSON结构？
# A: 使用 validate_json_object 或自定义验证器
@validate_params({
    'data': {
        'type': dict,
        'required': True,
        'validator': lambda d: validate_json_object(d, required_fields=['name', 'value']),
        'source': 'json'
    }
})

# Q4: 如何保持向后兼容？
# A: 保持相同的响应字段，只是包装在统一格式中
# 旧格式: {'stocks': [...], 'count': 10}
# 新格式: {'success': true, 'stocks': [...], 'count': 10}

# Q5: 如何处理文件上传？
# A: 文件上传不使用 validate_params，直接使用 request.files
@app.route('/api/upload', methods=['POST'])
@handle_errors
def upload_file():
    if 'file' not in request.files:
        raise ValidationError("缺少文件")
    file = request.files['file']
    # 处理文件...
    return success_response(message='上传成功')


"""
步骤7: 性能优化建议
"""

# 1. 缓存验证结果（对于重复验证的参数）
# 2. 使用数据库连接池
# 3. 对大数据量查询使用流式响应
# 4. 添加请求限流（rate limiting）
# 5. 使用 Redis 缓存热点数据


"""
步骤8: 监控和日志
"""

# 添加请求日志装饰器
from .decorators import log_request

@app.route('/api/important-endpoint')
@log_request
@handle_errors
@validate_params({...})
def important_endpoint():
    pass

# 查看日志
# tail -f logs/api.log | grep ERROR
