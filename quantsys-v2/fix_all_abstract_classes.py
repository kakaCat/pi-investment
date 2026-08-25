#!/usr/bin/env python3
"""批量修复所有抽象类实例化问题"""
import re
import sys
import os

# 扫描所有 application/services 目录下的 Python 文件
service_dir = "application/services"
files_to_fix = []

for root, dirs, files in os.walk(service_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            files_to_fix.append(filepath)

# 匹配所有 "xxx = yyy or IXxxRepository()" 或 "xxx = yyy or IXxxService()" 的模式
# 并替换为 "xxx = yyy"
pattern = re.compile(
    r'(\s+)(self\.[_a-z0-9]+)\s*=\s*([a-z_0-9]+)\s+or\s+I[A-Z][a-zA-Z]*(?:Repository|Service)\(\)',
    re.MULTILINE
)

fixed_count = 0
error_count = 0

for filepath in files_to_fix:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 替换模式: self.xxx = yyy or IXxxRepository() -> self.xxx = yyy
        content = pattern.sub(r'\1\2 = \3', content)

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {filepath}")
            fixed_count += 1
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        error_count += 1

print(f"\n{'='*60}")
print(f"✅ Fixed {fixed_count} files")
if error_count > 0:
    print(f"❌ Errors: {error_count}")
print(f"{'='*60}")
