"""
数据质量API路由

提供数据质量查询和统计接口
"""

from flask import Blueprint, request, jsonify
from typing import Optional
import logging

from adapters.outbound.repositories import DataQualityORMRepository

logger = logging.getLogger(__name__)

# 创建蓝图
data_quality_bp = Blueprint('data_quality', __name__, url_prefix='/api/data')


@data_quality_bp.route('/quality-report', methods=['GET'])
def get_quality_report():
    """
    获取数据质量报告

    Query Parameters:
        - symbol: 股票代码（可选）
        - start_date: 开始日期 YYYY-MM-DD（可选）
        - end_date: 结束日期 YYYY-MM-DD（可选）
        - min_score: 最低评分 0-100（可选）
        - max_score: 最高评分 0-100（可选）
        - grade: 质量评级 A+/A/B/C/D（可选）
        - limit: 返回数量（默认100）
        - offset: 偏移量（默认0）

    Returns:
        {
            "success": true,
            "data": {
                "records": [...],
                "total": 100,
                "limit": 100,
                "offset": 0
            }
        }
    """
    try:
        # 获取查询参数
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        grade = request.args.get('grade')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # 限制最大返回数量
        limit = min(limit, 1000)

        # 查询数据
        repository = DataQualityORMRepository()
        records = repository.get_quality_records(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            min_score=min_score,
            max_score=max_score,
            grade=grade,
            limit=limit,
            offset=offset,
        )

        return jsonify({
            'success': True,
            'data': {
                'records': records,
                'total': len(records),
                'limit': limit,
                'offset': offset,
                'filters': {
                    'symbol': symbol,
                    'start_date': start_date,
                    'end_date': end_date,
                    'min_score': min_score,
                    'max_score': max_score,
                    'grade': grade,
                }
            }
        })

    except Exception as e:
        logger.error(f"获取质量报告失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/quality-stats', methods=['GET'])
def get_quality_stats():
    """
    获取数据质量统计

    Query Parameters:
        - symbol: 股票代码（可选，为空表示全局统计）
        - start_date: 开始日期 YYYY-MM-DD（可选）
        - end_date: 结束日期 YYYY-MM-DD（可选）
        - limit: 返回天数（默认30）

    Returns:
        {
            "success": true,
            "data": {
                "stats": [...],
                "symbol": "600519.SH" or null
            }
        }
    """
    try:
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 30, type=int)

        repository = DataQualityORMRepository()
        stats = repository.get_daily_stats(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return jsonify({
            'success': True,
            'data': {
                'stats': stats,
                'symbol': symbol,
            }
        })

    except Exception as e:
        logger.error(f"获取质量统计失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/quality-summary', methods=['GET'])
def get_quality_summary():
    """
    获取数据质量摘要

    Query Parameters:
        - days: 统计天数（默认7）

    Returns:
        {
            "success": true,
            "data": {
                "total_checks": 1234,
                "avg_score": 92.5,
                "grade_distribution": {
                    "A+": 100,
                    "A": 200,
                    "B": 50,
                    "C": 10,
                    "D": 5
                },
                "top_issues": [
                    {"type": "outlier", "count": 50},
                    {"type": "missing_field", "count": 20}
                ],
                "period": "Last 7 days"
            }
        }
    """
    try:
        days = request.args.get('days', 7, type=int)

        repository = DataQualityORMRepository()
        summary = repository.get_quality_summary(days=days)

        return jsonify({
            'success': True,
            'data': summary
        })

    except Exception as e:
        logger.error(f"获取质量摘要失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/quality-trend', methods=['GET'])
def get_quality_trend():
    """
    获取数据质量趋势（用于图表）

    Query Parameters:
        - symbol: 股票代码（可选）
        - days: 统计天数（默认30）

    Returns:
        {
            "success": true,
            "data": {
                "dates": ["2024-01-01", "2024-01-02", ...],
                "scores": [95.2, 93.1, ...],
                "error_counts": [5, 3, ...],
                "warning_counts": [10, 8, ...]
            }
        }
    """
    try:
        symbol = request.args.get('symbol')
        days = request.args.get('days', 30, type=int)

        repository = DataQualityORMRepository()
        stats = repository.get_daily_stats(
            symbol=symbol,
            limit=days,
        )

        # 反转顺序（从旧到新）
        stats.reverse()

        # 提取趋势数据
        dates = [s['date'] for s in stats]
        scores = [s['avg_overall'] for s in stats]
        error_counts = [s['total_errors'] for s in stats]
        warning_counts = [s['total_warnings'] for s in stats]

        return jsonify({
            'success': True,
            'data': {
                'dates': dates,
                'scores': scores,
                'error_counts': error_counts,
                'warning_counts': warning_counts,
                'symbol': symbol,
            }
        })

    except Exception as e:
        logger.error(f"获取质量趋势失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/quality-record/<int:record_id>', methods=['GET'])
def get_quality_record_detail(record_id: int):
    """
    获取单条质量记录详情

    Path Parameters:
        - record_id: 记录ID

    Returns:
        {
            "success": true,
            "data": {
                "id": 123,
                "symbol": "600519.SH",
                ...
            }
        }
    """
    try:
        repository = DataQualityORMRepository()
        records = repository.get_quality_records(limit=1, offset=0)

        # 这里简化处理，实际应该按ID查询
        # 需要在 repository 中添加 get_by_id 方法

        return jsonify({
            'success': True,
            'data': records[0] if records else None
        })

    except Exception as e:
        logger.error(f"获取质量记录详情失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/quality-submit', methods=['POST'])
def submit_quality_record():
    """
    提交质量记录（供TypeScript Agent调用）

    Request Body:
        {
            "symbol": "600519.SH",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "limit": 100,
            "original_count": 100,
            "cleaned_count": 98,
            "removed_count": 2,
            "fixed_count": 1,
            "error_count": 2,
            "warning_count": 3,
            "errors": [...],
            "warnings": [...],
            "cleaning_operations": [...],
            "completeness_score": 98.0,
            "consistency_score": 99.0,
            "accuracy_score": 97.0,
            "overall_score": 98.0,
            "grade": "A (良好)",
            "duration_ms": 15
        }

    Returns:
        {
            "success": true,
            "data": {
                "record_id": 123
            }
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '请求体不能为空'
            }), 400

        # 验证必填字段
        required_fields = ['symbol', 'period', 'original_count', 'cleaned_count',
                          'completeness_score', 'consistency_score', 'accuracy_score', 'overall_score']

        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'缺少必填字段: {field}'
                }), 400

        # 保存到数据库
        repository = DataQualityORMRepository()
        record_id = repository.save_quality_record(data)

        return jsonify({
            'success': True,
            'data': {
                'record_id': record_id,
                'message': '质量记录保存成功'
            }
        })

    except Exception as e:
        logger.error(f"提交质量记录失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================
# 新增：数据补救管理端点（2026-06-04）
# ========================================

@data_quality_bp.route('/check', methods=['GET'])
def check_data_quality_v2():
    """检查数据质量（新版）

    Query Parameters:
        symbols: 股票代码列表（逗号分隔，可选）
        start_date: 开始日期 (YYYY-MM-DD，可选)
        end_date: 结束日期 (YYYY-MM-DD，可选)
        include_report: 是否生成详细报告 (true/false，可选)

    Returns:
        JSON response with quality check results
    """
    try:
        from application.services.data_quality_service import DataQualityService

        # 解析参数
        symbols_str = request.args.get('symbols')
        symbols = symbols_str.split(',') if symbols_str else None
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        include_report = request.args.get('include_report', 'false').lower() == 'true'

        logger.info(f"检查数据质量v2: symbols={symbols}, dates={start_date}~{end_date}")

        # 执行检查
        service = DataQualityService()
        result = service.check_data_quality(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            include_report=include_report
        )

        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        logger.error(f"检查数据质量失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/detect-gaps', methods=['POST'])
def detect_gaps():
    """检测缺失数据

    Request Body:
        {
            "symbols": ["600000.SH", "000001.SZ"],  // 可选
            "start_date": "2026-01-01",              // 可选
            "end_date": "2026-06-04"                 // 可选
        }

    Returns:
        JSON response with gap detection results
    """
    try:
        from application.services.data_quality_service import DataQualityService

        data = request.get_json() or {}
        symbols = data.get('symbols')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        logger.info(f"检测缺失数据: {len(symbols) if symbols else 'all'} stocks")

        service = DataQualityService()
        result = service.detect_missing_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        logger.error(f"检测缺失数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/backfill', methods=['POST'])
def backfill_data():
    """补充缺失数据

    Request Body:
        {
            "symbols": ["600000.SH"],      // 可选
            "start_date": "2026-01-01",    // 可选
            "end_date": "2026-06-04",      // 可选
            "mode": "auto",                // auto | force
            "max_workers": 8               // 可选
        }

    Returns:
        JSON response with backfill results
    """
    try:
        from application.services.data_quality_service import DataQualityService

        data = request.get_json() or {}
        symbols = data.get('symbols')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        mode = data.get('mode', 'auto')
        max_workers = data.get('max_workers', 8)

        logger.info(f"补充缺失数据: {len(symbols) if symbols else 'all'} stocks, mode={mode}")

        service = DataQualityService()
        result = service.backfill_missing_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            max_workers=max_workers
        )

        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        logger.error(f"补充缺失数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/validate', methods=['POST'])
def validate_data_v2():
    """验证数据质量

    Request Body:
        {
            "symbols": ["600000.SH"],      // 可选
            "start_date": "2026-01-01",    // 可选
            "end_date": "2026-06-04"       // 可选
        }

    Returns:
        JSON response with validation results
    """
    try:
        from application.services.data_quality_service import DataQualityService

        data = request.get_json() or {}
        symbols = data.get('symbols')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        logger.info(f"验证数据质量: {len(symbols) if symbols else 'all'} stocks")

        service = DataQualityService()
        result = service.validate_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        logger.error(f"验证数据质量失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
