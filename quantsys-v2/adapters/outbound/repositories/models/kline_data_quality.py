"""
K线数据质量记录模型

用于持久化数据质量检测结果，支持历史追踪和趋势分析
复用现有的 psycopg2 数据库连接
"""

from datetime import datetime
from typing import Dict, Any, Optional

# 不使用 SQLAlchemy，直接使用 psycopg2
# 表结构通过 SQL 创建

class QualityGrade:
    """质量评级常量"""
    A_PLUS = "A+"  # 优秀 >= 95%
    A = "A"        # 良好 >= 90%
    B = "B"        # 合格 >= 80%
    C = "C"        # 一般 >= 70%
    D = "D"        # 较差 < 70%

    @classmethod
    def from_score(cls, score: float) -> str:
        """根据评分返回评级"""
        if score >= 95:
            return cls.A_PLUS
        elif score >= 90:
            return cls.A
        elif score >= 80:
            return cls.B
        elif score >= 70:
            return cls.C
        else:
            return cls.D


# SQL 表创建语句
CREATE_KLINE_QUALITY_TABLE = """
CREATE TABLE IF NOT EXISTS kline_data_quality (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    period VARCHAR(20) NOT NULL,
    start_date VARCHAR(10),
    end_date VARCHAR(10),
    limit_count INTEGER,
    original_count INTEGER NOT NULL,
    cleaned_count INTEGER NOT NULL,
    removed_count INTEGER DEFAULT 0,
    fixed_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    errors_json JSONB,
    warnings_json JSONB,
    cleaning_operations_json JSONB,
    completeness_score FLOAT NOT NULL,
    consistency_score FLOAT NOT NULL,
    accuracy_score FLOAT NOT NULL,
    overall_score FLOAT NOT NULL,
    grade VARCHAR(10) NOT NULL,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kline_quality_symbol ON kline_data_quality(symbol);
CREATE INDEX IF NOT EXISTS idx_kline_quality_score ON kline_data_quality(overall_score);
CREATE INDEX IF NOT EXISTS idx_kline_quality_grade ON kline_data_quality(grade);
CREATE INDEX IF NOT EXISTS idx_kline_quality_created ON kline_data_quality(created_at);
"""

CREATE_QUALITY_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS data_quality_stats (
    id SERIAL PRIMARY KEY,
    date VARCHAR(10) NOT NULL,
    symbol VARCHAR(20),
    total_requests INTEGER DEFAULT 0,
    total_records INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    total_warnings INTEGER DEFAULT 0,
    total_removed INTEGER DEFAULT 0,
    total_fixed INTEGER DEFAULT 0,
    avg_completeness FLOAT,
    avg_consistency FLOAT,
    avg_accuracy FLOAT,
    avg_overall FLOAT,
    grade_a_plus_count INTEGER DEFAULT 0,
    grade_a_count INTEGER DEFAULT 0,
    grade_b_count INTEGER DEFAULT 0,
    grade_c_count INTEGER DEFAULT 0,
    grade_d_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quality_stats_date ON data_quality_stats(date);
CREATE INDEX IF NOT EXISTS idx_quality_stats_symbol ON data_quality_stats(symbol);
CREATE UNIQUE INDEX IF NOT EXISTS idx_quality_stats_unique ON data_quality_stats(date, COALESCE(symbol, ''));
"""


def format_quality_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """格式化质量记录"""
    return {
        'id': row['id'],
        'symbol': row['symbol'],
        'period': row['period'],
        'start_date': row['start_date'],
        'end_date': row['end_date'],
        'limit': row['limit_count'],
        'original_count': row['original_count'],
        'cleaned_count': row['cleaned_count'],
        'removed_count': row['removed_count'],
        'fixed_count': row['fixed_count'],
        'error_count': row['error_count'],
        'warning_count': row['warning_count'],
        'errors': row['errors_json'],
        'warnings': row['warnings_json'],
        'cleaning_operations': row['cleaning_operations_json'],
        'completeness_score': row['completeness_score'],
        'consistency_score': row['consistency_score'],
        'accuracy_score': row['accuracy_score'],
        'overall_score': row['overall_score'],
        'grade': row['grade'],
        'duration_ms': row['duration_ms'],
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
    }


def format_quality_stats(row: Dict[str, Any]) -> Dict[str, Any]:
    """格式化统计数据"""
    return {
        'id': row['id'],
        'date': row['date'],
        'symbol': row['symbol'],
        'total_requests': row['total_requests'],
        'total_records': row['total_records'],
        'total_errors': row['total_errors'],
        'total_warnings': row['total_warnings'],
        'total_removed': row['total_removed'],
        'total_fixed': row['total_fixed'],
        'avg_completeness': row['avg_completeness'],
        'avg_consistency': row['avg_consistency'],
        'avg_accuracy': row['avg_accuracy'],
        'avg_overall': row['avg_overall'],
        'grade_distribution': {
            'A+': row['grade_a_plus_count'],
            'A': row['grade_a_count'],
            'B': row['grade_b_count'],
            'C': row['grade_c_count'],
            'D': row['grade_d_count'],
        },
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
    }
