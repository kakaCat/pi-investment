-- ============================================================
-- Migration: 002_add_ml_models_table
-- Description: ML模型注册表，持久化训练元数据与指标
-- Created: 2026-05-24
-- ============================================================

CREATE TABLE IF NOT EXISTS quant.ml_models (
    id                  SERIAL PRIMARY KEY,
    model_type          VARCHAR(50)  NOT NULL,
    version             VARCHAR(100) NOT NULL,
    model_path          TEXT,
    train_accuracy      DOUBLE PRECISION,
    test_accuracy       DOUBLE PRECISION,
    precision           DOUBLE PRECISION,
    recall              DOUBLE PRECISION,
    f1_score            DOUBLE PRECISION,
    roc_auc             DOUBLE PRECISION,
    feature_count       INTEGER,
    train_samples       INTEGER,
    feature_importance  JSONB DEFAULT '{}',
    training_params     JSONB DEFAULT '{}',
    training_report     JSONB DEFAULT '{}',
    status              VARCHAR(20) DEFAULT 'ready',
    train_date          TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_type, version)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ml_models_type ON quant.ml_models(model_type);
CREATE INDEX IF NOT EXISTS idx_ml_models_status ON quant.ml_models(status);
CREATE INDEX IF NOT EXISTS idx_ml_models_train_date ON quant.ml_models(train_date DESC);

-- Comments
COMMENT ON TABLE quant.ml_models IS 'ML模型注册表——存储训练元数据、指标与文件路径';
COMMENT ON COLUMN quant.ml_models.model_type IS '模型类型: xgboost, lightgbm';
COMMENT ON COLUMN quant.ml_models.version IS '版本标识，格式 YYYYMMDD_HHMMSS';
COMMENT ON COLUMN quant.ml_models.model_path IS '模型文件路径（.pkl）';
COMMENT ON COLUMN quant.ml_models.feature_importance IS '特征重要性 {feature_name: score}';
COMMENT ON COLUMN quant.ml_models.training_report IS '完整训练报告 JSON';
COMMENT ON COLUMN quant.ml_models.status IS 'training | ready | failed';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'quant' AND table_name = 'ml_models'
    ) THEN
        RAISE EXCEPTION 'Migration failed: ml_models table not created';
    END IF;
    RAISE NOTICE 'Migration 002_add_ml_models_table completed successfully';
END $$;
