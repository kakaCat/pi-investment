"""
测试 SearchSpace 参数网格生成器
"""
import pytest
from application.services.search_space import SearchSpace


class TestSearchSpace:
    """测试参数搜索空间"""

    def test_generates_grid_from_single_param(self):
        """测试单个参数生成网格"""
        space = SearchSpace({
            'fast': [5, 10, 20]
        })

        grid = space.generate_grid()

        assert len(grid) == 3
        assert {'fast': 5} in grid
        assert {'fast': 10} in grid
        assert {'fast': 20} in grid

    def test_generates_grid_from_multiple_params(self):
        """测试多个参数生成笛卡尔积网格"""
        space = SearchSpace({
            'fast': [5, 10],
            'slow': [20, 50]
        })

        grid = space.generate_grid()

        assert len(grid) == 4  # 2 * 2
        assert {'fast': 5, 'slow': 20} in grid
        assert {'fast': 5, 'slow': 50} in grid
        assert {'fast': 10, 'slow': 20} in grid
        assert {'fast': 10, 'slow': 50} in grid

    def test_generates_grid_with_three_params(self):
        """测试三个参数生成网格"""
        space = SearchSpace({
            'fast': [5, 10],
            'slow': [20, 30],
            'threshold': [0.5, 0.8]
        })

        grid = space.generate_grid()

        assert len(grid) == 8  # 2 * 2 * 2
        assert {'fast': 5, 'slow': 20, 'threshold': 0.5} in grid
        assert {'fast': 10, 'slow': 30, 'threshold': 0.8} in grid

    def test_empty_space_returns_empty_grid(self):
        """测试空搜索空间返回空网格"""
        space = SearchSpace({})

        grid = space.generate_grid()

        assert len(grid) == 0

    def test_single_value_per_param_returns_one_combination(self):
        """测试每个参数只有一个值时返回单个组合"""
        space = SearchSpace({
            'fast': [10],
            'slow': [50]
        })

        grid = space.generate_grid()

        assert len(grid) == 1
        assert grid[0] == {'fast': 10, 'slow': 50}
