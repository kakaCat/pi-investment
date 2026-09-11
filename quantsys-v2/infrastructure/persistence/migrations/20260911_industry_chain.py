"""迁移：产业链图谱三表（RFC 015 §2.5，REQ-cf627b，P2，2026-09-11）

为什么需要：
  RFC 015 缺口①（无产业链图谱）——2026-09-11 扫玻纤链时只能**手工硬编码**上下游成员，
  链式扫描（决策原则#4）实际不可执行。产业链拓扑与成员归位必须落库才能被反复查询、
  被复盘审计、被其他窗口复用。

三张表：
  quant.industry_chain         产业链（聚合根：chain_id/name/rationale/curator/source）
  quant.industry_chain_node    环节节点（upstream_of/downstream_of JSONB + keywords）
  quant.industry_chain_member  成员（唯一键 (chain_id, symbol, node_id)，含 evidence/confidence/as_of）

数据完整性（防"静默错数据"）：
  - exposure_ratio CHECK 0-1：上游若给百分数（97.3）而未归一，直接写不进去（fail-loud），
    避免重演 2026-09-11 分红 provider「读错列名→全 0→被当成不分红」的静默错误。
  - stage / confidence CHECK：枚举值受限，防止拼写错误悄悄入库。
  - symbol 外键 quant.stocks：不在股票表的代码不得入库。

用法：./venv/bin/python infrastructure/persistence/migrations/20260911_industry_chain.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DDL = [
    """CREATE TABLE IF NOT EXISTS quant.industry_chain (
         chain_id VARCHAR(80) PRIMARY KEY,
         name VARCHAR(200) NOT NULL,
         description TEXT,
         rationale TEXT,
         curator VARCHAR(80),
         source VARCHAR(40) NOT NULL DEFAULT 'curated',
         created_at TIMESTAMP DEFAULT NOW(),
         updated_at TIMESTAMP DEFAULT NOW()
       )""",
    "CREATE INDEX IF NOT EXISTS idx_industry_chain_updated ON quant.industry_chain (updated_at DESC)",

    """CREATE TABLE IF NOT EXISTS quant.industry_chain_node (
         id SERIAL PRIMARY KEY,
         chain_id VARCHAR(80) NOT NULL REFERENCES quant.industry_chain(chain_id) ON DELETE CASCADE,
         node_id VARCHAR(120) NOT NULL,
         name VARCHAR(200) NOT NULL,
         stage VARCHAR(20) NOT NULL,
         upstream_of JSONB,
         downstream_of JSONB,
         keywords JSONB,
         rationale TEXT,
         updated_at TIMESTAMP DEFAULT NOW(),
         CONSTRAINT uq_industry_chain_node UNIQUE (chain_id, node_id),
         CONSTRAINT chk_industry_chain_node_stage
           CHECK (stage IN ('upstream', 'midstream', 'downstream', 'terminal'))
       )""",
    "CREATE INDEX IF NOT EXISTS idx_industry_chain_node_stage ON quant.industry_chain_node (chain_id, stage)",

    """CREATE TABLE IF NOT EXISTS quant.industry_chain_member (
         id SERIAL PRIMARY KEY,
         chain_id VARCHAR(80) NOT NULL REFERENCES quant.industry_chain(chain_id) ON DELETE CASCADE,
         node_id VARCHAR(120) NOT NULL,
         symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
         name VARCHAR(80),
         stage VARCHAR(20) NOT NULL,
         role VARCHAR(40),
         exposure_ratio DOUBLE PRECISION,
         exposure_basis TEXT,
         exposure_as_of VARCHAR(20),
         evidence TEXT,
         evidence_kind VARCHAR(20),
         confidence VARCHAR(10),
         source VARCHAR(40),
         conflict TEXT,
         as_of TIMESTAMP DEFAULT NOW(),
         updated_at TIMESTAMP DEFAULT NOW(),
         CONSTRAINT uq_industry_chain_member UNIQUE (chain_id, symbol, node_id),
         CONSTRAINT chk_industry_chain_member_stage
           CHECK (stage IN ('upstream', 'midstream', 'downstream', 'terminal')),
         CONSTRAINT chk_industry_chain_member_confidence
           CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
         CONSTRAINT chk_industry_chain_member_ratio
           CHECK (exposure_ratio IS NULL OR (exposure_ratio >= 0 AND exposure_ratio <= 1))
       )""",
    "CREATE INDEX IF NOT EXISTS idx_industry_chain_member_symbol ON quant.industry_chain_member (symbol)",
    "CREATE INDEX IF NOT EXISTS idx_industry_chain_member_chain_node"
    " ON quant.industry_chain_member (chain_id, node_id)",
]


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)


def verify(cursor):
    for table in ('industry_chain', 'industry_chain_node', 'industry_chain_member'):
        cursor.execute(f"SELECT count(*) FROM quant.{table}")
        print(f"  quant.{table} 行数:", cursor.fetchone()[0])
    cursor.execute(
        """SELECT constraint_name FROM information_schema.table_constraints
           WHERE table_schema='quant' AND table_name='industry_chain_member'
             AND constraint_type='CHECK'"""
    )
    print("  member CHECK 约束:", sorted(r[0] for r in cursor.fetchall()))


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    cursor = conn.cursor()
    try:
        print("迁移：产业链图谱三表（RFC 015 §2.5）")
        upgrade(cursor)
        conn.commit()
        verify(cursor)
        print("✓ 完成")
    except Exception as e:
        conn.rollback()
        print("✗ 失败:", e)
        raise
    finally:
        cursor.close()
        conn.close()
