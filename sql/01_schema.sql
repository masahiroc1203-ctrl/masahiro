CREATE TABLE IF NOT EXISTS users (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS providers (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subcategories (
    id          SERIAL PRIMARY KEY,
    category_id INT REFERENCES categories(id),
    name        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (category_id, name)
);

CREATE TABLE IF NOT EXISTS transactions (
    id             BIGSERIAL PRIMARY KEY,
    user_id        INT            NOT NULL REFERENCES users(id),
    provider_id    INT            NOT NULL REFERENCES providers(id),
    category_id    INT            REFERENCES categories(id),
    subcategory_id INT            REFERENCES subcategories(id),
    amount         NUMERIC(12,2)  NOT NULL,
    currency       CHAR(3)        NOT NULL DEFAULT 'JPY',
    occurred_at    TIMESTAMPTZ    NOT NULL,
    memo           TEXT,
    created_at     TIMESTAMPTZ    DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transactions_occurred_at  ON transactions(occurred_at);
CREATE INDEX IF NOT EXISTS idx_transactions_provider_id  ON transactions(provider_id);
CREATE INDEX IF NOT EXISTS idx_transactions_category_id  ON transactions(category_id);
