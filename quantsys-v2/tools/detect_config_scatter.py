"""
配置分散检测工具

扫描项目中的配置位置：
- 环境变量读取 (os.getenv, os.environ)
- 硬编码配置值
- YAML/JSON 配置文件
- 数据库配置表
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ConfigUsage:
    """配置使用记录"""
    file_path: str
    line_number: int
    config_type: str  # 'env_var', 'hardcoded', 'yaml', 'db_query'
    key: str  # 配置键名
    default_value: str = ""
    code_snippet: str = ""


@dataclass
class ConfigAnalysisResult:
    """配置使用分析结果"""
    total_files: int = 0

    # 环境变量使用
    env_var_usages: List[ConfigUsage] = field(default_factory=list)

    # 硬编码配置
    hardcoded_configs: List[ConfigUsage] = field(default_factory=list)

    # 配置文件
    config_files: List[Path] = field(default_factory=list)

    # 按文件分组
    by_file: Dict[str, List[ConfigUsage]] = field(default_factory=lambda: defaultdict(list))


class ConfigUsageDetector(ast.NodeVisitor):
    """AST访问器：检测配置使用"""

    def __init__(self, file_path: str, source_lines: List[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.usages: List[ConfigUsage] = []

        # 常见硬编码配置模式
        self.hardcoded_patterns = {
            'pool_size', 'max_overflow', 'pool_recycle', 'pool_pre_ping',
            'max_workers', 'timeout', 'retry_times', 'batch_size',
            'port', 'host', 'database', 'max_connections',
        }

    def visit_Call(self, node: ast.Call):
        """访问函数调用"""
        # 检测 os.getenv / os.environ.get
        if isinstance(node.func, ast.Attribute):
            if self._is_env_access(node.func):
                self._record_env_var(node)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """访问赋值语句"""
        # 检测硬编码配置
        for target in node.targets:
            if isinstance(target, ast.Name):
                if self._is_config_name(target.id):
                    self._record_hardcoded(node, target.id)

        self.generic_visit(node)

    def _is_env_access(self, node: ast.Attribute) -> bool:
        """判断是否是环境变量访问"""
        # os.getenv, os.environ.get, os.environ[]
        if node.attr in {'getenv', 'get'}:
            if isinstance(node.value, ast.Name) and node.value.id == 'os':
                return True
            if isinstance(node.value, ast.Attribute):
                if node.value.attr == 'environ' and isinstance(node.value.value, ast.Name):
                    if node.value.value.id == 'os':
                        return True
        return False

    def _is_config_name(self, name: str) -> bool:
        """判断变量名是否像配置"""
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in self.hardcoded_patterns)

    def _record_env_var(self, node: ast.Call):
        """记录环境变量使用"""
        # 提取环境变量名
        if not node.args:
            return

        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant):
            env_key = first_arg.value
        elif isinstance(first_arg, ast.Str):  # Python 3.7 compatibility
            env_key = first_arg.s
        else:
            return

        # 提取默认值
        default_value = ""
        if len(node.args) > 1:
            default_arg = node.args[1]
            if isinstance(default_arg, (ast.Constant, ast.Str, ast.Num)):
                default_value = str(ast.literal_eval(default_arg))

        # 从关键字参数中提取 default
        for keyword in node.keywords:
            if keyword.arg == 'default':
                if isinstance(keyword.value, (ast.Constant, ast.Str, ast.Num)):
                    default_value = str(ast.literal_eval(keyword.value))

        line_number = node.lineno
        code_snippet = self.source_lines[line_number - 1].strip()

        usage = ConfigUsage(
            file_path=self.file_path,
            line_number=line_number,
            config_type='env_var',
            key=env_key,
            default_value=default_value,
            code_snippet=code_snippet,
        )

        self.usages.append(usage)

    def _record_hardcoded(self, node: ast.Assign, var_name: str):
        """记录硬编码配置"""
        # 提取值
        value_str = ""
        if isinstance(node.value, (ast.Constant, ast.Num, ast.Str)):
            value_str = str(ast.literal_eval(node.value))

        line_number = node.lineno
        code_snippet = self.source_lines[line_number - 1].strip()

        usage = ConfigUsage(
            file_path=self.file_path,
            line_number=line_number,
            config_type='hardcoded',
            key=var_name,
            default_value=value_str,
            code_snippet=code_snippet,
        )

        self.usages.append(usage)


def scan_file(file_path: Path) -> List[ConfigUsage]:
    """扫描单个文件"""
    try:
        source = file_path.read_text(encoding='utf-8')
        source_lines = source.splitlines(keepends=False)

        # 快速预检
        if 'getenv' not in source and 'environ' not in source:
            if not any(pattern in source.lower() for pattern in [
                'pool_size', 'max_workers', 'timeout', 'port', 'host'
            ]):
                return []

        tree = ast.parse(source, filename=str(file_path))
        detector = ConfigUsageDetector(str(file_path), source_lines)
        detector.visit(tree)

        return detector.usages

    except SyntaxError:
        return []
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}")
        return []


def find_config_files(root_dir: Path) -> List[Path]:
    """查找配置文件"""
    config_files = []

    # YAML 配置
    for yaml_file in root_dir.rglob('*.yaml'):
        if '.venv' not in yaml_file.parts and '__pycache__' not in yaml_file.parts:
            config_files.append(yaml_file)

    for yml_file in root_dir.rglob('*.yml'):
        if '.venv' not in yml_file.parts and '__pycache__' not in yml_file.parts:
            config_files.append(yml_file)

    # JSON 配置
    for json_file in root_dir.rglob('*.json'):
        if '.venv' not in json_file.parts and '__pycache__' not in json_file.parts:
            # 排除 package.json, tsconfig.json 等
            if 'config' in json_file.name.lower() or json_file.name in {'.env.json', 'settings.json'}:
                config_files.append(json_file)

    # .env 文件
    for env_file in root_dir.rglob('.env*'):
        if '.venv' not in env_file.parts:
            config_files.append(env_file)

    return config_files


def scan_project(root_dir: Path) -> ConfigAnalysisResult:
    """扫描整个项目"""
    result = ConfigAnalysisResult()

    # 扫描 Python 文件
    for py_file in root_dir.rglob('*.py'):
        if any(part in py_file.parts for part in ['.venv', 'venv', '__pycache__', '.git']):
            continue

        result.total_files += 1
        usages = scan_file(py_file)

        for usage in usages:
            if usage.config_type == 'env_var':
                result.env_var_usages.append(usage)
            elif usage.config_type == 'hardcoded':
                result.hardcoded_configs.append(usage)

            result.by_file[usage.file_path].append(usage)

    # 查找配置文件
    result.config_files = find_config_files(root_dir)

    return result


def print_report(result: ConfigAnalysisResult, verbose: bool = False):
    """打印分析报告"""
    print("=" * 80)
    print("配置分散检测报告")
    print("=" * 80)
    print()

    print(f"📊 扫描统计:")
    print(f"  - 扫描文件数: {result.total_files}")
    print(f"  - 环境变量使用: {len(result.env_var_usages)} 处")
    print(f"  - 硬编码配置: {len(result.hardcoded_configs)} 处")
    print(f"  - 配置文件: {len(result.config_files)} 个")
    print()

    # 环境变量统计
    print("🔑 环境变量使用 (前20):")
    env_var_counts = defaultdict(int)
    for usage in result.env_var_usages:
        env_var_counts[usage.key] += 1

    for key, count in sorted(env_var_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {key:40s} : {count:3d} 处")
    print()

    # 硬编码配置热点
    print("⚙️  硬编码配置热点 (前20):")
    hardcoded_counts = defaultdict(int)
    for usage in result.hardcoded_configs:
        hardcoded_counts[usage.key] += 1

    for key, count in sorted(hardcoded_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {key:40s} : {count:3d} 处")
    print()

    # 配置文件列表
    print("📁 配置文件:")
    for config_file in sorted(result.config_files):
        # 显示相对路径
        try:
            rel_path = config_file.relative_to(Path.cwd())
        except ValueError:
            rel_path = config_file
        print(f"  - {rel_path}")
    print()

    # 推荐方案
    print("=" * 80)
    print("💡 推荐统一配置方案")
    print("=" * 80)
    print()
    print("使用 Pydantic Settings 统一管理配置：")
    print()
    print("""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class AppSettings(BaseSettings):
    \"\"\"应用配置（统一入口）\"\"\"

    # 数据库
    database_url: str
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    # Redis
    redis_url: Optional[str] = None

    # Agent OS
    agent_os_url: str = "http://localhost:3002"

    # 线程池
    default_pool_workers: int = 10
    io_pool_workers: int = 20
    compute_pool_workers: int = 4

    # 调度器
    scheduler_tick_interval: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

# 全局配置实例
settings = AppSettings()
""")
    print()
    print("使用示例：")
    print("""
# BEFORE: 分散的配置读取
pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))

# AFTER: 统一配置
from infrastructure.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)
""")
    print()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='检测项目中的配置分散情况')
    parser.add_argument('--root', type=str, default='.',
                        help='项目根目录 (默认: 当前目录)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细信息')

    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    if not root_dir.exists():
        print(f"Error: Directory not found: {args.root}")
        return 1

    result = scan_project(root_dir)
    print_report(result, verbose=args.verbose)

    return 0


if __name__ == '__main__':
    exit(main())
