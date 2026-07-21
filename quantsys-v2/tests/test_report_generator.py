# tests/test_report_generator.py
import pytest
from application.services.report_generator import ReportGenerator, ReportGenerationError
from pathlib import Path
import os
import time

def test_generate_report():
    """测试生成 Markdown 报告"""
    generator = ReportGenerator()

    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'good',
            'risk': 'moderate',
            'stability': 'good'
        }
    }

    diagnosis = {
        'conclusion': '策略表现良好',
        'strengths': ['夏普比率优于基准'],
        'weaknesses': ['最大回撤偏高'],
        'suggestions': ['添加动态止损']
    }

    params = {
        'strategyName': 'ma_cross',
        'symbol': '000001.SZ',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }

    report_path = generator.generate(analysis, diagnosis, params)

    assert report_path.startswith('docs/superpowers/reports/')
    assert report_path.endswith('.md')
    assert Path(report_path).exists()

    # 验证报告内容
    content = Path(report_path).read_text()
    assert '策略诊断报告' in content
    assert 'ma_cross' in content
    assert '000001.SZ' in content
    assert '夏普比率' in content

    # 清理测试文件
    Path(report_path).unlink()


def test_generate_report_with_empty_diagnosis_lists():
    """测试空诊断列表"""
    generator = ReportGenerator()

    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'good',
            'risk': 'moderate',
            'stability': 'good'
        }
    }

    diagnosis = {
        'conclusion': '策略表现中性',
        'strengths': [],
        'weaknesses': [],
        'suggestions': []
    }

    params = {
        'strategyName': 'test_strategy',
        'symbol': '600000.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }

    report_path = generator.generate(analysis, diagnosis, params)

    assert Path(report_path).exists()
    content = Path(report_path).read_text()
    assert '策略表现中性' in content
    assert '### 优势' in content
    assert '### 劣势' in content
    assert '### 优化建议' in content

    # 清理测试文件
    Path(report_path).unlink()


def test_generate_report_with_invalid_rating():
    """测试无效评级值"""
    generator = ReportGenerator()

    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'unknown_rating',
            'risk': 'invalid',
            'stability': 'good'
        }
    }

    diagnosis = {
        'conclusion': '测试无效评级',
        'strengths': ['测试'],
        'weaknesses': ['测试'],
        'suggestions': ['测试']
    }

    params = {
        'strategyName': 'test_strategy',
        'symbol': '600000.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }

    report_path = generator.generate(analysis, diagnosis, params)

    assert Path(report_path).exists()
    content = Path(report_path).read_text()
    # 无效评级应该原样显示
    assert 'unknown_rating' in content
    assert 'invalid' in content

    # 清理测试文件
    Path(report_path).unlink()


def test_generate_report_with_special_characters_in_filename():
    """测试文件名中的特殊字符"""
    generator = ReportGenerator()

    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'good',
            'risk': 'moderate',
            'stability': 'good'
        }
    }

    diagnosis = {
        'conclusion': '测试特殊字符',
        'strengths': ['测试'],
        'weaknesses': ['测试'],
        'suggestions': ['测试']
    }

    params = {
        'strategyName': 'test/strategy:with*special?chars',
        'symbol': '600000.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }

    report_path = generator.generate(analysis, diagnosis, params)

    assert Path(report_path).exists()
    # 验证特殊字符被清理
    assert '/' not in Path(report_path).name
    assert ':' not in Path(report_path).name
    assert '*' not in Path(report_path).name
    assert '?' not in Path(report_path).name

    # 清理测试文件
    Path(report_path).unlink()


def test_generate_report_no_overwrite_same_day():
    """测试同一天多次生成不会覆盖"""
    generator = ReportGenerator()

    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'good',
            'risk': 'moderate',
            'stability': 'good'
        }
    }

    diagnosis1 = {
        'conclusion': '第一次诊断',
        'strengths': ['测试1'],
        'weaknesses': ['测试1'],
        'suggestions': ['测试1']
    }

    diagnosis2 = {
        'conclusion': '第二次诊断',
        'strengths': ['测试2'],
        'weaknesses': ['测试2'],
        'suggestions': ['测试2']
    }

    params = {
        'strategyName': 'test_strategy',
        'symbol': '600000.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }

    # 生成第一个报告
    report_path1 = generator.generate(analysis, diagnosis1, params)
    content1 = Path(report_path1).read_text()
    assert '第一次诊断' in content1

    # 延迟至少 1 秒确保时间戳不同（格式为 YYYY-MM-DD-HHMMSS）
    time.sleep(1.1)

    # 生成第二个报告
    report_path2 = generator.generate(analysis, diagnosis2, params)
    content2 = Path(report_path2).read_text()
    assert '第二次诊断' in content2

    # 验证两个文件不同
    assert report_path1 != report_path2
    assert Path(report_path1).exists()
    assert Path(report_path2).exists()

    # 清理测试文件
    Path(report_path1).unlink()
    Path(report_path2).unlink()


def test_generate_report_missing_required_keys():
    """测试缺少必填字段"""
    generator = ReportGenerator()

    # 缺少 metrics
    with pytest.raises(ReportGenerationError, match="Missing required key"):
        generator.generate(
            {'benchmark': {}, 'ratings': {}},
            {'conclusion': '', 'strengths': [], 'weaknesses': [], 'suggestions': []},
            {'strategyName': 'test', 'symbol': '600000.SH', 'startDate': '2024-01-01', 'endDate': '2024-12-31'}
        )

    # 缺少 params.strategyName
    with pytest.raises(ReportGenerationError, match="Missing required key"):
        generator.generate(
            {'metrics': {}, 'benchmark': {}, 'ratings': {}},
            {'conclusion': '', 'strengths': [], 'weaknesses': [], 'suggestions': []},
            {'symbol': '600000.SH', 'startDate': '2024-01-01', 'endDate': '2024-12-31'}
        )


def test_generate_report_write_permission_error(tmp_path):
    """测试文件写入权限错误"""
    # 创建只读目录
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o444)

    generator = ReportGenerator(output_dir=str(readonly_dir))

    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'good',
            'risk': 'moderate',
            'stability': 'good'
        }
    }

    diagnosis = {
        'conclusion': '测试权限错误',
        'strengths': ['测试'],
        'weaknesses': ['测试'],
        'suggestions': ['测试']
    }

    params = {
        'strategyName': 'test_strategy',
        'symbol': '600000.SH',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }

    with pytest.raises(ReportGenerationError, match="Failed to write report"):
        generator.generate(analysis, diagnosis, params)

    # 恢复权限以便清理
    readonly_dir.chmod(0o755)
