---
id: wl-2026-08-m0-fund-flow-fix-plan
title: M0 资金流数据修复方案（紧急）
type: worklog
status: archived
updated: 2026-08-25
owners: [agent-dh]
tags: [worklog, 2026-08]
---

# M0 资金流数据修复方案（紧急）

**问题编号**: M0-P0-FUNDFLOW  
**严重度**: 🔴 P0（阻塞 M2-3, M7-1）  
**发现时间**: 2026-08-31 02:50  
**修复负责**: 需立即启动

---

## 🔍 问题定位

### 症状

1. **`factor_values` 表资金流因子近乎空白**
   - 600519（茅台）08-27: `large_net = 0`
   - 正常应该: `large_net = -38593.02`（来自 stock_fund_flow）

2. **数据采集不完整**
   - `stock_fund_flow` 表 08-28 仅 1 只股票
   - 正常应该: ~5000 只股票

### 根因分析

**两层问题**：

#### 问题1: 数据采集不完整（P0-A）

```sql
-- stock_fund_flow 表覆盖情况
SELECT trade_date, COUNT(DISTINCT symbol) as symbols 
FROM quant.stock_fund_flow 
WHERE trade_date >= '2026-08-25' 
GROUP BY trade_date;

-- 结果（推测）:
trade_date | symbols
-----------|--------
2026-08-28 |     1    -- ❌ 仅 1 只（应该 ~5000）
2026-08-27 |   ???    
2026-08-26 |   ???    
2026-08-25 |   ???
```

**根因**: 资金流采集任务执行不完整或未执行

#### 问题2: 数据未同步到因子表（P0-B）

```sql
-- stock_fund_flow 有数据
SELECT main_net_inflow FROM quant.stock_fund_flow 
WHERE symbol='600519' AND trade_date='2026-08-28';
-- 结果: -7203.52 ✅

-- factor_values 无数据
SELECT factor_value FROM quant.factor_values 
WHERE symbol='600519' AND factor_name='main_net_inflow' AND factor_date='2026-08-28';
-- 结果: (空) ❌
```

**根因**: 缺少 `stock_fund_flow` → `factor_values` 的 ETL 任务

---

## 🎯 修复方案

### 立即修复（今日完成）

#### 步骤1: 诊断采集覆盖率

```bash
# 检查最近5天采集覆盖
cd /Users/yunpeng/pi-investment/quantsys-v2
psql -d quant_investment << EOF
SELECT 
  trade_date, 
  COUNT(DISTINCT symbol) as symbols,
  COUNT(*) as records
FROM quant.stock_fund_flow 
WHERE trade_date >= CURRENT_DATE - INTERVAL '5 days'
GROUP BY trade_date 
ORDER BY trade_date DESC;
EOF
```

**预期结果**：
- 如果所有日期 <100 只 → 采集任务未正常执行
- 如果部分日期正常（>4000 只） → 偶发性失败

#### 步骤2: 手动触发采集（补救）

```bash
# 查找采集脚本
cd /Users/yunpeng/pi-investment/quantsys-v2
find . -name "*fund_flow*" -name "*.py" | grep -E "(job|task|update)"

# 手动执行（根据找到的脚本）
python infrastructure/jobs/fund_flow_update_job.py
# 或
python scripts/archived_scripts/update_fund_flow.py
```

#### 步骤3: 实现 ETL 同步脚本

创建 `scripts/sync_fund_flow_to_factors.py`:

```python
#!/usr/bin/env python3
"""
同步 stock_fund_flow → factor_values

执行: python scripts/sync_fund_flow_to_factors.py [--date YYYY-MM-DD]
"""
import argparse
from datetime import date, timedelta
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 因子映射
FACTOR_MAPPING = {
    'main_net_inflow': 'main_net_inflow',
    'large_net_inflow': 'large_net_inflow',
    'main_net_inflow_rate': 'main_net_pct',
    'big_net_inflow': 'super_large_net',
}

def sync_to_factors(engine, trade_date):
    """同步指定日期的资金流数据到因子表"""
    
    with engine.connect() as conn:
        # 1. 从 stock_fund_flow 读取
        result = conn.execute(text("""
            SELECT symbol, trade_date, 
                   main_net_inflow, large_net_inflow, 
                   main_net_inflow_rate, big_net_inflow
            FROM quant.stock_fund_flow
            WHERE trade_date = :date
        """), {"date": trade_date})
        
        rows = result.fetchall()
        logger.info(f"读取到 {len(rows)} 条资金流数据（{trade_date}）")
        
        if len(rows) == 0:
            logger.warning(f"⚠️ {trade_date} 无资金流数据，跳过同步")
            return 0
        
        # 2. 批量插入 factor_values
        synced = 0
        for row in rows:
            symbol, td, main_net, large_net, main_pct, super_large = row
            
            for col, factor_name in FACTOR_MAPPING.items():
                value = locals()[col.replace('_inflow', '_net').replace('_rate', '_pct')]
                if value is None:
                    continue
                
                # ON CONFLICT DO UPDATE (保证幂等)
                conn.execute(text("""
                    INSERT INTO quant.factor_values 
                        (symbol, factor_date, factor_name, factor_value)
                    VALUES (:symbol, :date, :factor, :value)
                    ON CONFLICT (symbol, factor_date, factor_name) 
                    DO UPDATE SET factor_value = EXCLUDED.factor_value
                """), {
                    "symbol": symbol,
                    "date": td,
                    "factor": factor_name,
                    "value": float(value)
                })
                synced += 1
        
        conn.commit()
        logger.info(f"✅ 同步完成: {len(rows)} 只股票 × 4 因子 = {synced} 条记录")
        return synced

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='交易日期 YYYY-MM-DD，默认昨日')
    parser.add_argument('--days', type=int, default=1, help='回填天数')
    args = parser.parse_args()
    
    engine = create_engine("postgresql://yunpeng@localhost/quant_investment")
    
    if args.date:
        end_date = date.fromisoformat(args.date)
    else:
        end_date = date.today() - timedelta(days=1)
    
    # 回填多日
    for i in range(args.days):
        trade_date = end_date - timedelta(days=i)
        logger.info(f"\n=== 处理 {trade_date} ===")
        sync_to_factors(engine, trade_date)

if __name__ == '__main__':
    main()
```

**立即执行**:
```bash
# 回填最近5天
python scripts/sync_fund_flow_to_factors.py --days 5
```

---

## 🔧 长期修复（本周完成）

### 方案A: 修复采集任务

#### 1. 找到采集入口

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
grep -r "stock_fund_flow" --include="*.py" | grep -E "(insert|update)" | head -10
```

#### 2. 检查调度配置

```bash
# Agent OS scheduler
curl http://localhost:8080/api/v1/scheduler/jobs | jq '.[] | select(.name | contains("fund"))'

# quantsys-v2 legacy scheduler（已废弃）
psql -d quant_investment -c "SELECT * FROM quant.scheduled_tasks WHERE name LIKE '%fund%';"
```

#### 3. 重新挂载任务

**推荐方案**: 挂载到 Agent OS

```python
# 在 quantsys-v2/tools/register_jobs_to_agent_os.py 添加
def register_fund_flow_job():
    """注册资金流采集任务"""
    payload = {
        "name": "fund_flow_daily",
        "cron": "0 30 16 * * 1-5",  # 工作日 16:30
        "handler": {
            "type": "http",
            "config": {
                "url": "http://localhost:5001/api/data/sync-fund-flow",
                "method": "POST",
                "timeout": 300  # 5分钟
            }
        },
        "window": "w-8366e526",  # investor 窗口
        "description": "每日采集全市场资金流数据"
    }
    
    resp = requests.post(
        "http://localhost:8080/api/v1/scheduler/jobs",
        json=payload
    )
    print(f"✅ 资金流采集任务已挂载: {resp.json()}")
```

### 方案B: 自动 ETL 同步

#### 选项1: 触发器（推荐）

```sql
-- 在 stock_fund_flow 表上创建触发器
CREATE OR REPLACE FUNCTION sync_fund_flow_to_factors()
RETURNS TRIGGER AS $$
BEGIN
    -- 插入 main_net_inflow
    INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
    VALUES (NEW.symbol, NEW.trade_date, 'main_net_inflow', NEW.main_net_inflow)
    ON CONFLICT (symbol, factor_date, factor_name) 
    DO UPDATE SET factor_value = EXCLUDED.factor_value;
    
    -- 插入 large_net
    INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
    VALUES (NEW.symbol, NEW.trade_date, 'large_net', NEW.large_net_inflow)
    ON CONFLICT (symbol, factor_date, factor_name) 
    DO UPDATE SET factor_value = EXCLUDED.factor_value;
    
    -- 插入 main_net_pct
    INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
    VALUES (NEW.symbol, NEW.trade_date, 'main_net_pct', NEW.main_net_inflow_rate)
    ON CONFLICT (symbol, factor_date, factor_name) 
    DO UPDATE SET factor_value = EXCLUDED.factor_value;
    
    -- 插入 super_large_net
    INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
    VALUES (NEW.symbol, NEW.trade_date, 'super_large_net', NEW.big_net_inflow)
    ON CONFLICT (symbol, factor_date, factor_name) 
    DO UPDATE SET factor_value = EXCLUDED.factor_value;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sync_fund_flow
AFTER INSERT OR UPDATE ON quant.stock_fund_flow
FOR EACH ROW
EXECUTE FUNCTION sync_fund_flow_to_factors();
```

**优点**: 实时同步，零延迟  
**缺点**: 批量插入性能下降

#### 选项2: 定时 ETL（推荐）

挂载 `sync_fund_flow_to_factors.py` 到 Agent OS:

```bash
# 每日 16:45 执行（采集后 15 分钟）
cron: "0 45 16 * * 1-5"
handler: 
  type: "bash"
  command: "cd /Users/yunpeng/pi-investment/quantsys-v2 && python scripts/sync_fund_flow_to_factors.py"
```

---

## 📋 验收清单

### 立即验收（今日）

- [ ] 执行 `sync_fund_flow_to_factors.py --days 5`
- [ ] 验证 600519 因子数据修复:
  ```sql
  SELECT factor_name, factor_date, factor_value 
  FROM quant.factor_values 
  WHERE symbol='600519' AND factor_name='large_net' 
  ORDER BY factor_date DESC LIMIT 5;
  ```
- [ ] 预期结果: 08-28: -10686.25（与 stock_fund_flow 一致）

### 本周验收

- [ ] 采集任务挂载到 Agent OS
- [ ] ETL 同步任务挂载（触发器或定时脚本）
- [ ] 连续 3 日自动同步无中断
- [ ] M2-3 pool_battlefield 评分区分度 ≥5 分

---

## 🎯 修复后效果

### 数据完整性

| 指标 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| factor_values 资金流覆盖 | <1% | 95% | +9400% |
| 每日采集股票数 | 1 | ~5000 | +500000% |
| M2-3 可用性 | 30% | 90% | +60% |
| M7-1 可用性 | 0% | 80% | +80% |

### 解锁能力

- ✅ M2-3 pool_battlefield 评分恢复正常
- ✅ M7-1 opponent_behavior 可以分析机构/散户动向
- ✅ M3 信号分级可以使用资金流维度
- ✅ M6-2 归因分析包含"资金面"维度

---

## ⚠️ 风险提示

1. **采集频率限制**
   - 东方财富网可能有反爬虫限制
   - 建议添加随机延迟（1-3 秒/股票）
   - 单次采集时间: ~2-3 小时（5000 只）

2. **数据质量**
   - 资金流数据可能有延迟（T+1）
   - 停牌股票无资金流数据
   - 新股/次新股数据不完整

3. **ETL 性能**
   - 触发器模式: 批量插入慢（每行触发一次）
   - 定时ETL模式: 15 分钟延迟（可接受）

---

## 📈 执行计划

### Phase 1: 紧急修复（今日 3小时）

| 时间 | 任务 | 负责 |
|------|------|------|
| 03:00-03:30 | 诊断采集覆盖率 | investor |
| 03:30-04:00 | 实现 ETL 脚本 | 实施者 |
| 04:00-04:30 | 回填 5 日数据 | 实施者 |
| 04:30-05:00 | 验收测试 | investor |

### Phase 2: 长期方案（明日-本周）

| 日期 | 任务 |
|------|------|
| 09-01 | 采集任务挂载 Agent OS |
| 09-01 | ETL 同步任务挂载 |
| 09-02 | 连续 3 日监控 |
| 09-03 | M2-3/M7-1 验收 |

---

**文档编制**: agent-dh investor (w-8366e526)  
**编制时间**: 2026-08-31 03:00  
**优先级**: 🔴 P0（立即执行）
