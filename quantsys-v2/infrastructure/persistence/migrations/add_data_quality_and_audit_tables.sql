-- 2026-07-19 修复：为补全的 ORM 仓储创建缺失的表
-- 1) quant.data_quality_records — DataQualityORMRepository
-- 2) quant.operation_audit — TraceabilityORMRepository

CREATE TABLE IF NOT EXISTS quant.data_quality_records (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    period VARCHAR(20) DEFAULT 'daily',
    check_date DATE NOT NULL DEFAULT CURRENT_DATE,
    start_date DATE,
    end_date DATE,

    original_count INTEGER,
    cleaned_count INTEGER,
    removed_count INTEGER,
    fixed_count INTEGER,
    error_count INTEGER,
    warning_count INTEGER,

    errors JSONB,
    warnings JSONB,
    cleaning_operations JSONB,

    completeness_score DOUBLE PRECISION,
    consistency_score DOUBLE PRECISION,
    accuracy_score DOUBLE PRECISION,
    overall_score DOUBLE PRECISION,
    grade VARCHAR(20),

    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dq_records_symbol ON quant.data_quality_records(symbol);
CREATE INDEX IF NOT EXISTS idx_dq_records_check_date ON quant.data_quality_records(check_date);
CREATE INDEX IF NOT EXISTS idx_dq_records_grade ON quant.data_quality_records(grade);

COMMENT ON TABLE quant.data_quality_records IS '数据质量检查记录表';

CREATE TABLE IF NOT EXISTS quant.operation_audit (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    actor VARCHAR(100) DEFAULT 'agent',
    detail JSONB,
    result VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operation_audit_type ON quant.operation_audit(operation_type);
CREATE INDEX IF NOT EXISTS idx_operation_audit_created ON quant.operation_audit(created_at);

COMMENT ON TABLE quant.operation_audit IS '操作审计日志表（可追溯性）';
