"""test_security.py — Tests for SQLGlot AST validation, allowlists, and injection prevention."""

import pytest
from query_engine import validate_sql


def test_reject_dml_delete():
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        validate_sql("DELETE FROM invoices WHERE id = 1")


def test_reject_dml_drop():
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        validate_sql("DROP TABLE customers")


def test_reject_dml_update():
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        validate_sql("UPDATE invoices SET total_amount = 0")


def test_reject_dml_insert():
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        validate_sql("INSERT INTO products (product_id, name) VALUES ('P1', 'Test')")


def test_reject_multi_statement():
    with pytest.raises(ValueError, match="Expected exactly 1 SQL statement"):
        validate_sql("SELECT 1 FROM customers; DROP TABLE invoices")


def test_reject_copy():
    with pytest.raises(ValueError):
        validate_sql("COPY invoices TO '/tmp/data.csv'")


def test_reject_select_into():
    with pytest.raises(ValueError, match="SELECT INTO"):
        validate_sql("SELECT * INTO backup_invoices FROM invoices")


def test_reject_system_schemas():
    with pytest.raises(ValueError, match="Access to schema 'pg_catalog' is forbidden"):
        validate_sql("SELECT * FROM pg_catalog.pg_tables")

    with pytest.raises(ValueError, match="Access to schema 'information_schema' is forbidden"):
        validate_sql("SELECT * FROM information_schema.tables")


def test_reject_unknown_tables():
    with pytest.raises(ValueError, match="not in the allowed tables list"):
        validate_sql("SELECT * FROM passwords")

    with pytest.raises(ValueError, match="not in the allowed tables list"):
        validate_sql("SELECT * FROM users")


def test_reject_unknown_columns():
    with pytest.raises(ValueError, match="Column 'password'"):
        validate_sql("SELECT password FROM customers")

    with pytest.raises(ValueError, match="Column 'secret_token'"):
        validate_sql("SELECT c.secret_token FROM customers AS c")


def test_reject_blocked_functions():
    with pytest.raises(ValueError, match="PG_SLEEP"):
        validate_sql("SELECT PG_SLEEP(5) FROM customers")

    with pytest.raises(ValueError, match="PG_READ_FILE"):
        validate_sql("SELECT PG_READ_FILE('/etc/passwd') FROM customers")


def test_limit_enforcement_missing():
    sql = "SELECT customer_id, name FROM customers"
    result = validate_sql(sql)
    assert "LIMIT 100" in result.upper()


def test_limit_enforcement_excessive():
    sql = "SELECT customer_id, name FROM customers LIMIT 5000"
    result = validate_sql(sql)
    assert "LIMIT 100" in result.upper()
    assert "5000" not in result


def test_limit_enforcement_retains_smaller_limit():
    sql = "SELECT customer_id, name FROM customers LIMIT 10"
    result = validate_sql(sql)
    assert "LIMIT 10" in result.upper()


def test_parameter_binding_validation():
    # Missing parameter
    with pytest.raises(ValueError, match="missing from parameters dict"):
        validate_sql("SELECT * FROM invoices WHERE payment_status = :status", {})

    # Extra parameter
    with pytest.raises(ValueError, match="not found in query placeholders"):
        validate_sql(
            "SELECT * FROM invoices WHERE payment_status = :status",
            {"status": "paid", "extra_param": "foo"},
        )

    # Valid parameter match
    valid_sql = validate_sql(
        "SELECT * FROM invoices WHERE payment_status = :status",
        {"status": "paid"},
    )
    assert ":status" in valid_sql
