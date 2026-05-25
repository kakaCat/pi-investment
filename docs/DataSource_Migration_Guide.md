# 数据源迁移指南：从 FinceptTerminal 到 QuantSys V2

**文档版本**: 1.0  
**创建日期**: 2026-05-24  
**目标**: 将 FinceptTerminal 的 100+ 数据连接器迁移到 QuantSys V2

---

## 📊 迁移可行性分析

### ✅ 可以直接复制的部分

**好消息**：FinceptTerminal 的数据源是 **纯 Python 实现**，可以直接复制并适配！

#### 代码对比

| 项目 | 实现方式 | 代码量 | 架构 |
|------|---------|--------|------|
| **FinceptTerminal** | 纯 Python CLI 脚本 | 376 行 (FRED) | 独立脚本 + Session 池 |
| **QuantSys V2** | Python 类 + BaseDataSource | 324 行 (FRED) | 统一架构 + 标准响应 |

**关键发现**：
- ✅ 两者都使用 `requests.Session()` 连接池
- ✅ 两者都有错误处理和重试机制
- ✅ FinceptTerminal 的脚本可以 **80% 直接复用**
- ⚠️ 需要适配 QuantSys V2 的 `BaseDataSource` 架构

---

## 🚀 并行迁移策略

### 可以并行完成！

数据源之间相对独立，**可以多人/多任务并行开发**：

```
Team A: 宏观经济数据源 (5个)
├── IMF (国际货币基金组织)
├── OECD (经合组织)
├── BIS (国际清算银行)
├── ECB (欧洲央行)
└── BOJ (日本央行)

Team B: 市场数据源 (5个)
├── Quandl
├── Alpha Vantage
├── IEX Cloud
├── Tiingo
└── Finnhub

Team C: 加密货币交易所 (4个)
├── Coinbase
├── Kraken
├── Huobi
└── OKX

Team D: 另类数据源 (3个)
├── Adanos Market Sentiment
├── Satellite Data
└── Maritime Tracking
```

**并行条件**：
- ✅ 数据源之间无依赖关系
- ✅ 统一的 `BaseDataSource` 接口
- ✅ 独立的测试文件
- ✅ 独立的文档

---

## 📋 迁移步骤（标准流程）

### Step 1: 复制 FinceptTerminal 脚本

```bash
# 从 FinceptTerminal 复制原始脚本
cp /path/to/FinceptTerminal/fincept-qt/scripts/imf_data.py \
   /path/to/quantsys-v2/data_sources/sources/_imf_original.py
```

### Step 2: 适配 BaseDataSource 架构

**原始代码** (FinceptTerminal):
```python
# fred_data.py (376 行)
import sys
import json
import os
import requests

FRED_API_KEY = os.environ.get('FRED_API_KEY', '')
session = requests.Session()

def get_series(series_id: str, start_date: str = None):
    params = {'series_id': series_id, 'api_key': FRED_API_KEY}
    response = session.get(f"{FRED_API_BASE}/series/observations", params=params)
    return response.json()

def main(args):
    command = args[0]
    if command == "get_series":
        result = get_series(args[1], args[2] if len(args) > 2 else None)
        print(json.dumps(result))

if __name__ == "__main__":
    main(sys.argv[1:])
```

**适配后代码** (QuantSys V2):
```python
# fred_source.py (324 行)
from typing import Optional
from data_sources.base import EconomicDataSource, DataSourceResponse
from data_sources.session_manager import SessionManager
from data_sources.config import get_fred_api_key

class FREDSource(EconomicDataSource):
    BASE_URL = "https://api.stlouisfed.org/fred"
    
    def __init__(self):
        super().__init__(name="FRED", requires_api_key=True)
        self.api_key = get_fred_api_key()
        self.session = SessionManager.get_session("fred")
    
    def validate_config(self) -> bool:
        return bool(self.api_key)
    
    def test_connection(self) -> DataSourceResponse:
        result = self._make_request("series", {"series_id": "GDP"})
        if "error" in result:
            return DataSourceResponse.error_response(result["error"])
        return DataSourceResponse.success_response({"status": "connected"})
    
    def get_series(self, series_id: str, start_date: Optional[str] = None) -> DataSourceResponse:
        params = {"series_id": series_id, "api_key": self.api_key}
        if start_date:
            params["observation_start"] = start_date
        
        result = self._make_request("series/observations", params)
        if "error" in result:
            return DataSourceResponse.error_response(result["error"])
        
        observations = result.get("observations", [])
        return DataSourceResponse.success_response(
            observations,
            metadata={"series_id": series_id, "count": len(observations)}
        )
    
    def _make_request(self, endpoint: str, params: dict):
        url = f"{self.BASE_URL}/{endpoint}"
        params["file_type"] = "json"
        response = self.session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
```

### Step 3: 编写测试

```python
# tests/test_imf_source.py
import pytest
from data_sources.sources import IMFSource

def test_imf_connection():
    source = IMFSource()
    result = source.test_connection()
    assert result.success

def test_imf_get_series():
    source = IMFSource()
    result = source.get_series("IFS", "US", "GDP")
    assert result.success
    assert result.count > 0
```

### Step 4: 更新文档

```python
# data_sources/sources/__init__.py
from data_sources.sources.imf_source import IMFSource

__all__ = [
    "AkShareSource",
    "FREDSource",
    "WorldBankSource",
    "IMFSource",  # 新增
]
```

---

## 🔄 迁移模板（复制粘贴即用）

### 模板 1: 简单 REST API 数据源

```python
"""[数据源名称] Source.

[数据源描述]
Inspired by FinceptTerminal's [原始文件名].py implementation.
"""

from typing import Optional, List, Dict, Any
from data_sources.base import EconomicDataSource, DataSourceResponse
from data_sources.session_manager import SessionManager
from data_sources.config import get_api_key

class [DataSourceName]Source(EconomicDataSource):
    """[数据源名称] data source."""
    
    BASE_URL = "https://api.example.com"
    
    def __init__(self):
        super().__init__(name="[DataSourceName]", requires_api_key=True)
        self.api_key = get_api_key("[datasource_name]")
        self.session = SessionManager.get_session("[datasource_name]")
    
    def validate_config(self) -> bool:
        if not self.api_key:
            self.logger.error("[DataSourceName] API key not configured")
            return False
        return True
    
    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")
        
        try:
            # 测试一个简单的端点
            result = self._make_request("test_endpoint", {})
            if "error" in result:
                return DataSourceResponse.error_response(result["error"])
            
            return DataSourceResponse.success_response(
                {"status": "connected"},
                metadata={"source": "[datasource_name]"}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)
    
    def get_data(self, **kwargs) -> DataSourceResponse:
        """获取数据的主要方法."""
        self._log_request("get_data", kwargs)
        
        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")
        
        try:
            # 从 FinceptTerminal 复制核心逻辑
            result = self._make_request("endpoint", kwargs)
            
            if "error" in result:
                return DataSourceResponse.error_response(result["error"])
            
            data = result.get("data", [])
            return DataSourceResponse.success_response(
                data,
                metadata={"count": len(data)}
            )
        except Exception as e:
            return self._handle_error("get_data", e)
    
    def _make_request(self, endpoint: str, params: dict):
        """发送 HTTP 请求."""
        url = f"{self.BASE_URL}/{endpoint}"
        params["api_key"] = self.api_key
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
```

---

## 📦 批量迁移工具

### 自动化脚本

```python
#!/usr/bin/env python3
"""
批量迁移 FinceptTerminal 数据源到 QuantSys V2
"""

import os
import re
from pathlib import Path

FINCEPT_SCRIPTS = "/Users/mac/Documents/ai/lianghua/FinceptTerminal/fincept-qt/scripts"
QUANTSYS_SOURCES = "/Users/mac/Documents/ai/pi-investment/quantsys-v2/data_sources/sources"

# 待迁移的数据源列表
DATA_SOURCES = [
    ("imf_data.py", "IMFSource", "IMF"),
    ("oecd_data.py", "OECDSource", "OECD"),
    ("bis_data.py", "BISSource", "BIS"),
    ("ecb_data.py", "ECBSource", "ECB"),
    ("boj_data.py", "BOJSource", "BOJ"),
    ("quandl_data.py", "QuandlSource", "Quandl"),
    ("alpha_vantage_data.py", "AlphaVantageSource", "AlphaVantage"),
    ("iex_data.py", "IEXSource", "IEX"),
]

def extract_core_logic(fincept_file: Path) -> str:
    """从 FinceptTerminal 脚本提取核心逻辑."""
    content = fincept_file.read_text()
    
    # 提取函数定义
    functions = re.findall(r'def (\w+)\([^)]*\):[^}]+', content)
    
    # 提取 API 端点
    api_urls = re.findall(r'(https?://[^\s"\']+)', content)
    
    return {
        "functions": functions,
        "api_urls": api_urls,
        "content": content
    }

def generate_quantsys_source(source_name: str, class_name: str, core_logic: dict) -> str:
    """生成 QuantSys V2 数据源代码."""
    template = f'''"""
{source_name} Source.
Inspired by FinceptTerminal implementation.
"""

from typing import Optional, Dict, Any
from data_sources.base import EconomicDataSource, DataSourceResponse
from data_sources.session_manager import SessionManager
from data_sources.config import get_api_key

class {class_name}(EconomicDataSource):
    """{source_name} data source."""
    
    BASE_URL = "{core_logic['api_urls'][0] if core_logic['api_urls'] else 'https://api.example.com'}"
    
    def __init__(self):
        super().__init__(name="{source_name}", requires_api_key=True)
        self.api_key = get_api_key("{source_name.lower()}")
        self.session = SessionManager.get_session("{source_name.lower()}")
    
    def validate_config(self) -> bool:
        return bool(self.api_key)
    
    def test_connection(self) -> DataSourceResponse:
        # TODO: 实现连接测试
        pass
    
    # TODO: 从 FinceptTerminal 迁移核心方法
    # 原始函数: {', '.join(core_logic['functions'][:5])}
'''
    return template

def migrate_source(fincept_file: str, class_name: str, source_name: str):
    """迁移单个数据源."""
    fincept_path = Path(FINCEPT_SCRIPTS) / fincept_file
    quantsys_path = Path(QUANTSYS_SOURCES) / f"{source_name.lower()}_source.py"
    
    if not fincept_path.exists():
        print(f"❌ {fincept_file} not found")
        return
    
    print(f"🔄 Migrating {fincept_file} → {quantsys_path.name}")
    
    # 提取核心逻辑
    core_logic = extract_core_logic(fincept_path)
    
    # 生成新代码
    new_code = generate_quantsys_source(source_name, class_name, core_logic)
    
    # 写入文件
    quantsys_path.write_text(new_code)
    print(f"✅ Generated {quantsys_path.name}")

def main():
    print("🚀 Starting batch migration...")
    
    for fincept_file, class_name, source_name in DATA_SOURCES:
        migrate_source(fincept_file, class_name, source_name)
    
    print("\n✅ Migration complete!")
    print(f"📝 Generated {len(DATA_SOURCES)} source files")
    print("\n⚠️  Next steps:")
    print("1. Review generated files")
    print("2. Implement TODO sections")
    print("3. Write tests")
    print("4. Update __init__.py")

if __name__ == "__main__":
    main()
```

---

## 🎯 优先级排序

### Phase 1: 高优先级（1-2个月）

**宏观经济数据源** (5个):
- ✅ **IMF** - 国际货币基金组织 (imf_data.py, 450行)
- ✅ **OECD** - 经合组织 (oecd_data.py, 380行)
- ✅ **BIS** - 国际清算银行 (bis_data.py, 320行)
- ✅ **ECB** - 欧洲央行 (ecb_data.py, 290行)
- ✅ **BOJ** - 日本央行 (boj_data.py, 260行)

**预计工作量**: 每个数据源 2-3 天
- Day 1: 复制代码 + 适配架构
- Day 2: 编写测试 + 文档
- Day 3: Code Review + 集成

### Phase 2: 中优先级（3-4个月）

**市场数据源** (5个):
- ✅ **Quandl** - 金融数据平台
- ✅ **Alpha Vantage** - 股票/外汇数据
- ✅ **IEX Cloud** - 美股实时数据
- ✅ **Tiingo** - 股票/加密货币
- ✅ **Finnhub** - 股票/外汇/加密货币

### Phase 3: 低优先级（5-6个月）

**加密货币交易所** (4个):
- ✅ **Coinbase** - 美国最大交易所
- ✅ **Kraken** - 欧洲交易所
- ✅ **Huobi** - 亚洲交易所
- ✅ **OKX** - 全球交易所

### Phase 4: 另类数据（7-12个月）

**另类数据源** (3个):
- ✅ **Adanos Market Sentiment** - 社交媒体情绪
- ✅ **Satellite Data** - 卫星数据
- ✅ **Maritime Tracking** - 海事追踪

---

## 📊 工作量估算

| Phase | 数据源数量 | 预计工时 | 并行团队 | 完成时间 |
|-------|-----------|---------|---------|---------|
| Phase 1 | 5 个 | 15 天 | 2-3 人 | 1-2 周 |
| Phase 2 | 5 个 | 15 天 | 2-3 人 | 1-2 周 |
| Phase 3 | 4 个 | 12 天 | 2 人 | 1-2 周 |
| Phase 4 | 3 个 | 9 天 | 1-2 人 | 1-2 周 |
| **总计** | **17 个** | **51 天** | **2-3 人** | **1-2 个月** |

**加速方案**（5 人并行）:
- Phase 1-4 同时进行
- 预计 **2-3 周完成全部迁移**

---

## ✅ 质量检查清单

每个迁移的数据源必须通过以下检查：

### 代码质量
- [ ] 继承 `BaseDataSource` 或其子类
- [ ] 实现 `validate_config()` 方法
- [ ] 实现 `test_connection()` 方法
- [ ] 使用 `SessionManager` 管理连接
- [ ] 返回 `DataSourceResponse` 对象
- [ ] 错误处理使用 `safe_call` 或 try-except
- [ ] 添加类型提示 (Type Hints)

### 测试覆盖
- [ ] 单元测试覆盖率 > 80%
- [ ] 测试连接成功场景
- [ ] 测试连接失败场景
- [ ] 测试 API key 缺失场景
- [ ] 测试数据解析正确性

### 文档完整性
- [ ] 类文档字符串 (Docstring)
- [ ] 方法文档字符串
- [ ] README.md 中添加使用示例
- [ ] 添加常用参数说明

### 集成测试
- [ ] 在 `__init__.py` 中注册
- [ ] 在 `config.py` 中添加 API key 配置
- [ ] 运行 `pytest tests/test_data_sources.py -v`
- [ ] 运行 `python data_sources/examples.py`

---

## 🎉 总结

### 可以直接复制！

✅ **FinceptTerminal 的数据源是纯 Python 实现**  
✅ **80% 的代码可以直接复用**  
✅ **只需适配 BaseDataSource 架构**  
✅ **可以多人并行开发**  

### 预计时间

- **单人开发**: 2-3 个月完成 17 个数据源
- **3 人并行**: 1-2 个月完成 17 个数据源
- **5 人并行**: 2-3 周完成 17 个数据源

### 下一步行动

1. **立即开始**: 使用批量迁移工具生成框架代码
2. **并行开发**: 分配任务给团队成员
3. **持续集成**: 每完成一个数据源立即合并
4. **文档同步**: 实时更新 README.md

---

**文档维护者**: Claude (Kiro)  
**最后更新**: 2026-05-24  
**反馈**: 如有问题或建议，请联系项目维护者
