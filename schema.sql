-- ============================================================
-- schema.sql — PostgreSQL DDL for Invoice Agent POC
-- ============================================================

-- Drop existing tables in reverse dependency order if recreating
-- DROP TABLE IF EXISTS invoices;
-- DROP TABLE IF EXISTS products;
-- DROP TABLE IF EXISTS customers;

-- 1. Create customers table
CREATE TABLE IF NOT EXISTS customers (
    customer_id   VARCHAR(32)  PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(150) UNIQUE NOT NULL,
    phone         VARCHAR(30),
    city          VARCHAR(80),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 2. Create products table
CREATE TABLE IF NOT EXISTS products (
    product_id     VARCHAR(32)   PRIMARY KEY,
    name           VARCHAR(150)  NOT NULL,
    category       VARCHAR(80)   NOT NULL,
    description    TEXT,
    price          NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    stock_quantity INTEGER       NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 3. Create invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id              SERIAL        PRIMARY KEY,
    invoice_number  VARCHAR(32)   UNIQUE NOT NULL,
    customer_id     VARCHAR(32)   NOT NULL REFERENCES customers(customer_id),
    invoice_date    DATE          NOT NULL,
    items           JSONB         NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    invoice_status  VARCHAR(32)   NOT NULL CHECK (invoice_status IN ('issued', 'void')),
    payment_status  VARCHAR(32)   NOT NULL CHECK (payment_status IN ('unpaid', 'partially_paid', 'paid', 'overdue')),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 4. Create least-privilege read-only role
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'poc_readonly_user') THEN
        CREATE ROLE poc_readonly_user WITH LOGIN PASSWORD 'readonly_pass';
    END IF;
END
$$;

-- Grant minimal permissions
GRANT USAGE ON SCHEMA public TO poc_readonly_user;
GRANT SELECT ON customers, products, invoices TO poc_readonly_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO poc_readonly_user;
