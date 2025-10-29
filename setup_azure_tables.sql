-- Setup Azure PostgreSQL Tables for S002 Sync
-- Run this ONCE on Azure PostgreSQL to create target tables
-- Database: gzc_platform

-- ==============================================================================
-- Table: gzc_cash_transactions
-- Source: tblCashTransaction (s002)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS gzc_cash_transactions (
    transaction_id INTEGER PRIMARY KEY,
    cashflow_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    fund_id INTEGER NOT NULL,
    counter_party VARCHAR(5) NOT NULL,
    account_type INTEGER NOT NULL,
    currency CHAR(3) NOT NULL,
    cashflow_type INTEGER NOT NULL,
    cash_amount NUMERIC(19,4) NOT NULL,
    trade_id INTEGER,
    asset_class_id INTEGER,
    instrument_type INTEGER,
    share_series_id INTEGER,
    mod_user VARCHAR(20) NOT NULL DEFAULT 'GZC',
    mod_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for gzc_cash_transactions
CREATE INDEX IF NOT EXISTS idx_gzc_cash_transactions_date
    ON gzc_cash_transactions(cashflow_date);

CREATE INDEX IF NOT EXISTS idx_gzc_cash_transactions_fund
    ON gzc_cash_transactions(fund_id);

CREATE INDEX IF NOT EXISTS idx_gzc_cash_transactions_currency
    ON gzc_cash_transactions(currency);

CREATE INDEX IF NOT EXISTS idx_gzc_cash_transactions_trade
    ON gzc_cash_transactions(trade_id) WHERE trade_id IS NOT NULL;

-- Table comment
COMMENT ON TABLE gzc_cash_transactions IS
    'Cash transactions synced from s002 GZCDB.tblCashTransaction';

-- ==============================================================================
-- Verify Tables Exist
-- ==============================================================================

-- List all sync tables
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('gzc_fx_trade', 'gzc_fx_option_trade', 'gzc_cash_transactions')
ORDER BY table_name;

-- Show record counts
SELECT 'gzc_fx_trade' as table_name, COUNT(*) as record_count FROM gzc_fx_trade
UNION ALL
SELECT 'gzc_fx_option_trade', COUNT(*) FROM gzc_fx_option_trade
UNION ALL
SELECT 'gzc_cash_transactions', COUNT(*) FROM gzc_cash_transactions;
