-- Seed schema for the backend. The backend also creates this on startup
-- (idempotent) but keeping it here documents the data model and lets Postgres
-- initialize even before the backend connects.
CREATE TABLE IF NOT EXISTS orders (
    id       SERIAL PRIMARY KEY,
    customer TEXT NOT NULL,
    item     TEXT NOT NULL,
    amount   NUMERIC(10,2) NOT NULL,
    created  TIMESTAMPTZ DEFAULT now()
);
