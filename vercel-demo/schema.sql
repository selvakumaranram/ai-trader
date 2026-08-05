CREATE TABLE IF NOT EXISTS holdings (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    buy_price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    buy_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_holdings_device_id ON holdings(device_id);

CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (device_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_device_id ON watchlist(device_id);

CREATE TABLE IF NOT EXISTS momentum_rankings (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    sector TEXT,
    pe_ratio NUMERIC,
    current_price NUMERIC NOT NULL,
    return_1d NUMERIC,
    return_3d NUMERIC,
    return_7d NUMERIC,
    return_1m NUMERIC,
    passes_quality_gates BOOLEAN NOT NULL,
    passes_trend_gate BOOLEAN NOT NULL,
    quality_gate_detail JSONB NOT NULL,
    momentum_score NUMERIC,
    volume_confirmation TEXT NOT NULL,
    stop_loss NUMERIC,
    target_low NUMERIC,
    target_high NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_momentum_rankings_run_date ON momentum_rankings(run_date);
