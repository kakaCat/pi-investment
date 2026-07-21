"""
统一的环境变量加载模块
在任何需要数据库连接的代码之前导入此模块
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 找到项目根目录的.env文件
root_dir = Path(__file__).parent
env_file = root_dir / '.env'

if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✅ 已加载环境变量: {env_file}")
else:
    print(f"⚠️  .env文件不存在: {env_file}")

# 验证关键环境变量
required_vars = ['QUANT_DATABASE_URL', 'DATABASE_URL', 'POSTGRES_DSN']
has_db_config = any(os.getenv(var) for var in required_vars)

if not has_db_config:
    # 如果都没有，尝试从PGDATABASE构造
    pgdb = os.getenv('PGDATABASE')
    if pgdb:
        db_url = f"postgresql://localhost/{pgdb}"
        os.environ['DATABASE_URL'] = db_url
        print(f"✅ 从PGDATABASE构造DATABASE_URL: {db_url}")
