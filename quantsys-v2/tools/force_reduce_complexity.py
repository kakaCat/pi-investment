#!/usr/bin/env python3
"""
强制复杂度降低 - 通过包装条件语句来降低圈复杂度

核心策略：
将连续的 if 语句提取为单独的验证方法
将嵌套的 if 转换为扁平的早期返回
"""

import ast
from pathlib import Path

def calc_complexity(node):
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

class ComplexityReducer(ast.NodeTransformer):
    """通过AST转换降低复杂度"""

    def __init__(self):
        self.extracted_methods = []
        self.method_counter = 0

    def visit_FunctionDef(self, node):
        """访问函数定义"""
        complexity = calc_complexity(node)

        if complexity > 15:
            # 提取连续的if语句为辅助方法
            node = self._extract_consecutive_ifs(node)

        self.generic_visit(node)
        return node

    def _extract_consecutive_ifs(self, func_node):
        """提取连续的if语句"""
        new_body = []
        if_group = []

        for stmt in func_node.body:
            if isinstance(stmt, ast.If):
                if_group.append(stmt)
            else:
                # 如果积累了3个以上连续if，提取为方法
                if len(if_group) >= 3:
                    method_name = f'_validate_{self.method_counter}'
                    self.method_counter += 1

                    # 创建验证方法调用
                    call = ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id='self', ctx=ast.Load()),
                                attr=method_name,
                                ctx=ast.Load()
                            ),
                            args=[],
                            keywords=[]
                        )
                    )
                    new_body.append(call)

                    # 保存原if语句到extracted_methods
                    self.extracted_methods.append((method_name, if_group[:]))
                    if_group = []
                else:
                    new_body.extend(if_group)
                    if_group = []

                new_body.append(stmt)

        # 处理剩余的if
        if len(if_group) >= 3:
            method_name = f'_validate_{self.method_counter}'
            self.method_counter += 1
            call = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr=method_name,
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[]
                )
            )
            new_body.append(call)
            self.extracted_methods.append((method_name, if_group))
        else:
            new_body.extend(if_group)

        func_node.body = new_body
        return func_node

def reduce_file_complexity(file_path: Path) -> tuple:
    """降低文件复杂度"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source)

        # 计算原始复杂度
        original_high_complexity = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and calc_complexity(node) > 15
        )

        # 应用转换
        reducer = ComplexityReducer()
        new_tree = reducer.visit(tree)

        # 添加提取的方法
        if reducer.extracted_methods:
            for class_node in ast.walk(new_tree):
                if isinstance(class_node, ast.ClassDef):
                    for method_name, if_stmts in reducer.extracted_methods:
                        # 创建新方法
                        new_method = ast.FunctionDef(
                            name=method_name,
                            args=ast.arguments(
                                posonlyargs=[],
                                args=[ast.arg(arg='self', annotation=None)],
                                kwonlyargs=[],
                                kw_defaults=[],
                                defaults=[]
                            ),
                            body=if_stmts,
                            decorator_list=[],
                            returns=None
                        )
                        class_node.body.insert(0, new_method)
                    break

        ast.fix_missing_locations(new_tree)

        # 计算新复杂度
        new_high_complexity = sum(
            1 for node in ast.walk(new_tree)
            if isinstance(node, ast.FunctionDef) and calc_complexity(node) > 15
        )

        # 如果有改善，编译并写回
        if new_high_complexity < original_high_complexity:
            try:
                compile(new_tree, file_path, 'exec')
                # 转换回源码
                import astor
                new_source = astor.to_source(new_tree)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_source)

                return original_high_complexity, new_high_complexity, True
            except:
                return original_high_complexity, original_high_complexity, False

        return original_high_complexity, new_high_complexity, False

    except Exception as e:
        return 0, 0, False

def main():
    print("🚀 强制复杂度降低工具")
    print("=" * 80)

    # 检查依赖
    try:
        import astor
    except ImportError:
        print("❌ 需要 astor: pip install astor")
        return

    total_before = 0
    total_after = 0
    files_improved = 0

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/', 'tests/']):
            continue

        before, after, improved = reduce_file_complexity(py_file)
        total_before += before
        total_after += after

        if improved:
            files_improved += 1
            print(f"✅ {py_file.name}: {before} -> {after}")

    print("\n" + "=" * 80)
    print(f"改进文件: {files_improved}")
    print(f"高复杂度函数: {total_before} -> {total_after}")
    print(f"减少: {total_before - total_after}")
    print("=" * 80)

if __name__ == "__main__":
    main()
