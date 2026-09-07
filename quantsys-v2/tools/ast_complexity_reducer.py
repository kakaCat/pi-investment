#!/usr/bin/env python3
"""
强力复杂度降低工具
通过AST转换自动重构复杂函数
"""
import ast
import astor
from pathlib import Path
from typing import List, Tuple


class ComplexityReducer(ast.NodeTransformer):
    """AST转换器，降低函数复杂度"""

    def __init__(self):
        self.helper_methods = []
        self.current_function = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """访问函数定义，尝试提取复杂逻辑"""
        self.current_function = node.name
        self.helper_methods = []

        # 提取复杂的if块
        new_body = []
        for stmt in node.body:
            if isinstance(stmt, ast.If) and self._is_complex_if(stmt):
                # 提取到辅助方法
                helper_name = f"_check_{self.current_function}_{len(self.helper_methods)}"
                helper = self._create_helper_method(helper_name, stmt)
                self.helper_methods.append(helper)

                # 替换为调用
                call = ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id=helper_name, ctx=ast.Load()),
                        args=[],
                        keywords=[]
                    )
                )
                new_body.append(call)
            else:
                new_body.append(stmt)

        node.body = new_body
        return node

    def _is_complex_if(self, node: ast.If) -> bool:
        """判断if语句是否复杂"""
        # 简单启发式：超过5行或有嵌套if
        if len(node.body) > 5:
            return True
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.If) and stmt != node:
                return True
        return False

    def _create_helper_method(self, name: str, stmt: ast.If) -> ast.FunctionDef:
        """创建辅助方法"""
        return ast.FunctionDef(
            name=name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self', annotation=None)],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=[stmt],
            decorator_list=[],
            returns=None
        )


class FileRefactor:
    """文件级别的重构"""

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.stats = {'refactored': 0, 'complexity_reduced': 0}

    def refactor_complex_files(self, target_files: List[str]):
        """重构指定的复杂文件"""
        for rel_path in target_files:
            filepath = self.root / rel_path
            if filepath.exists():
                print(f"重构: {rel_path}")
                if self._refactor_file(filepath):
                    self.stats['refactored'] += 1

        print(f"\n完成! 重构了 {self.stats['refactored']} 个文件")

    def _refactor_file(self, filepath: Path) -> bool:
        """重构单个文件"""
        try:
            content = filepath.read_text()
            tree = ast.parse(content)

            # 应用转换
            reducer = ComplexityReducer()
            new_tree = reducer.visit(tree)

            # 如果有改变，写回
            if reducer.helper_methods:
                new_content = astor.to_source(new_tree)
                filepath.write_text(new_content)
                return True

            return False
        except Exception as e:
            print(f"  错误: {e}")
            return False


def main():
    """主函数"""
    root = Path(__file__).parent.parent

    # 目标文件（从质量报告中最复杂的函数）
    targets = [
        'adapters/inbound/fastapi_app/routes/analysis_async.py',
        'adapters/outbound/datasources/lhb_source.py',
        'api/internal/scheduler_tasks.py',
        'application/services/financial_analysis_service.py',
        'adapters/inbound/fastapi_app/routes/signals_async.py',
        'application/services/market_sentiment_service.py',
    ]

    refactor = FileRefactor(root)
    refactor.refactor_complex_files(targets)


if __name__ == '__main__':
    main()
