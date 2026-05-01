-- Выполняется руками через psql или в Data Migration
-- CREATE INDEX CONCURRENTLY НЕЛЬЗЯ выполнять внутри транзакции!
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_symbol_created
ON trades_trade (symbol, created_at DESC NULLS LAST);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_exchange_id
ON trades_trade (exchange_id) WHERE exchange_id IS NOT NULL;