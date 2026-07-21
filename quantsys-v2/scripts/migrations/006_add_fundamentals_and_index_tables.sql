-- Migration 006: Add stock_fundamentals and index_constituents tables
-- Required for opportunity radar real-time scanning feature

-- Table: stock_fundamentals
-- Stores fundamental data for stocks (PE ratio, ROE, margins, etc.)
CREATE TABLE IF NOT EXISTS quant.stock_fundamentals (
    symbol TEXT PRIMARY KEY,
    pe_ratio DOUBLE PRECISION,
    roe DOUBLE PRECISION,
    gross_margin DOUBLE PRECISION,
    debt_ratio DOUBLE PRECISION,
    update_time DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stock_fundamentals_update_time
    ON quant.stock_fundamentals(update_time DESC);

COMMENT ON TABLE quant.stock_fundamentals IS 'Stock fundamental data for screening and analysis';
COMMENT ON COLUMN quant.stock_fundamentals.pe_ratio IS 'Price-to-Earnings ratio';
COMMENT ON COLUMN quant.stock_fundamentals.roe IS 'Return on Equity (decimal, e.g., 0.15 = 15%)';
COMMENT ON COLUMN quant.stock_fundamentals.gross_margin IS 'Gross profit margin (decimal)';
COMMENT ON COLUMN quant.stock_fundamentals.debt_ratio IS 'Debt-to-asset ratio (decimal)';

-- Table: index_constituents
-- Stores index constituent relationships (e.g., CSI 300, ChiNext)
CREATE TABLE IF NOT EXISTS quant.index_constituents (
    index_code TEXT NOT NULL,
    constituent_symbol TEXT NOT NULL,
    weight DOUBLE PRECISION DEFAULT 0,
    update_time TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (index_code, constituent_symbol)
);

CREATE INDEX IF NOT EXISTS idx_index_constituents_index_code
    ON quant.index_constituents(index_code);
CREATE INDEX IF NOT EXISTS idx_index_constituents_symbol
    ON quant.index_constituents(constituent_symbol);
CREATE INDEX IF NOT EXISTS idx_index_constituents_update_time
    ON quant.index_constituents(update_time DESC);

COMMENT ON TABLE quant.index_constituents IS 'Index constituent stocks mapping';
COMMENT ON COLUMN quant.index_constituents.index_code IS 'Index code (e.g., 000300.SH for CSI 300)';
COMMENT ON COLUMN quant.index_constituents.constituent_symbol IS 'Stock symbol in the index';
COMMENT ON COLUMN quant.index_constituents.weight IS 'Weight in the index (optional)';
