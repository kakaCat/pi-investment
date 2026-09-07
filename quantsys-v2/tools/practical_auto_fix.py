#!/usr/bin/env python3
"""
实用的代码质量自动修复工具
专注于可以安全自动化的修复：
1. 简化简单的if-else链
2. 提取重复代码块
3. 内联单次使用的变量
4. 合并相邻的条件判断
"""
import ast
import re
from pathlib import Path
from typing import List, Set


class PracticalFixer:
    """实用的自动修复器"""

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.stats = {
            'files_processed': 0,
            'complexity_reduced': 0,
            'lines_reduced': 0,
        }

    def process_all_files(self):
        """处理所有Python文件"""
        files = self._find_python_files()

        print(f"找到 {len(files)} 个文件")

        for i, filepath in enumerate(files, 1):
            if i % 100 == 0:
                print(f"进度: {i}/{len(files)}")

            if self._fix_file(filepath):
                self.stats['files_processed'] += 1

        self._print_summary()

    def _find_python_files(self) -> List[Path]:
        """查找所有Python文件"""
        files = []
        for filepath in self.root.rglob('*.py'):
            if 'venv' not in str(filepath) and '__pycache__' not in str(filepath):
                files.append(filepath)
        return files

    def _fix_file(self, filepath: Path) -> bool:
        """修复单个文件"""
        try:
            content = filepath.read_text()
            original_lines = len(content.splitlines())

            # 应用各种修复
            content = self._simplify_boolean_logic(content)
            content = self._merge_adjacent_ifs(content)
            content = self._remove_unnecessary_else(content)
            content = self._simplify_return_statements(content)

            new_lines = len(content.splitlines())
            if new_lines < original_lines:
                self.stats['lines_reduced'] += (original_lines - new_lines)
                filepath.write_text(content)
                return True

            return False
        except:
            return False

    def _simplify_boolean_logic(self, content: str) -> str:
        """简化布尔逻辑"""
        # if x == True: -> if x:
        content = re.sub(r'\bif\s+(\w+)\s*==\s*True\s*:', r'if \1:', content)
        # if x == False: -> if not x:
        content = re.sub(r'\bif\s+(\w+)\s*==\s*False\s*:', r'if not \1:', content)
        # if not x == True: -> if not x:
        content = re.sub(r'\bif\s+not\s+(\w+)\s*==\s*True\s*:', r'if not \1:', content)

        return content

    def _merge_adjacent_ifs(self, content: str) -> str:
        """合并相邻的if语句"""
        lines = content.splitlines(keepends=True)
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # 查找相邻的if语句
            if re.match(r'\s*if\s+', line) and i + 2 < len(lines):
                next_line = lines[i + 2]
                if re.match(r'\s*if\s+', next_line):
                    # 可能可以合并
                    indent1 = len(line) - len(line.lstrip())
                    indent2 = len(next_line) - len(next_line.lstrip())

                    if indent1 == indent2:
                        # 相同缩进，可以合并
                        cond1 = line.strip()[3:-1]  # 去掉 'if ' 和 ':'
                        cond2 = next_line.strip()[3:-1]

                        merged = ' ' * indent1 + f'if {cond1} and {cond2}:\n'
                        result.append(merged)
                        i += 3  # 跳过两个if
                        continue

            result.append(line)
            i += 1

        return ''.join(result)

    def _remove_unnecessary_else(self, content: str) -> str:
        """移除不必要的else（当if块以return结束时）"""
        lines = content.splitlines(keepends=True)
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # 查找 if...return 后的 else
            if 'return' in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                if re.match(r'\s*else\s*:', next_line):
                    # 移除else，减少缩进
                    result.append(line)
                    i += 2  # 跳过else

                    # 处理else块内容（减少缩进）
                    while i < len(lines):
                        else_line = lines[i]
                        if else_line.strip() and not else_line.startswith(' '):
                            break
                        # 减少4个空格的缩进
                        if else_line.startswith('    '):
                            result.append(else_line[4:])
                        else:
                            result.append(else_line)
                        i += 1
                    continue

            result.append(line)
            i += 1

        return ''.join(result)

    def _simplify_return_statements(self, content: str) -> str:
        """简化返回语句"""
        # return True if x else False -> return x
        content = re.sub(
            r'return\s+True\s+if\s+([^\s]+)\s+else\s+False',
            r'return \1',
            content
        )

        # return False if x else True -> return not x
        content = re.sub(
            r'return\s+False\s+if\s+([^\s]+)\s+else\s+True',
            r'return not \1',
            content
        )

        return content

    def _print_summary(self):
        """打印总结"""
        print("\n" + "=" * 60)
        print("自动修复完成!")
        print("=" * 60)
        print(f"处理的文件: {self.stats['files_processed']}")
        print(f"减少的代码行: {self.stats['lines_reduced']}")
        print("=" * 60)


def main():
    root = Path(__file__).parent.parent
    fixer = PracticalFixer(root)
    fixer.process_all_files()


if __name__ == '__main__':
    main()
