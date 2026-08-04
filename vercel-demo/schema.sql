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
