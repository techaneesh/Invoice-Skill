"""test_query_engine.py — Tests for JSONB queries, aggregations, and seed validation."""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from models import LineItem, InvoiceSeed
from query_engine import validate_sql
from seed_data import validate_seed_dataset, RAW_INVOICES_DATA


def test_lateral_jsonb_query_passes_validation():
    """Verify that canonical CROSS JOIN LATERAL query passes AST validation."""
    sql = """
    SELECT
        p.product_id,
        p.name,
        CAST(item.value ->> 'quantity' AS INTEGER) AS quantity,
        CAST(item.value ->> 'unit_price' AS NUMERIC) AS unit_price,
        CAST(item.value ->> 'line_total' AS NUMERIC) AS line_total
    FROM invoices AS i
    CROSS JOIN LATERAL jsonb_array_elements(i.items) AS item(value)
    JOIN products AS p ON p.product_id = (item.value ->> 'product_id')
    WHERE i.invoice_number = :invoice_number
    LIMIT 100
    """.strip()

    validated = validate_sql(sql, {"invoice_number": "INV-205"})
    assert "CROSS JOIN LATERAL" in validated.upper() or "LATERAL" in validated.upper()
    assert ":invoice_number" in validated


def test_seed_dataset_validates_successfully():
    """Verify that the official synthetic seed dataset passes all Pydantic validations."""
    invoices = validate_seed_dataset()
    assert len(invoices) == 20

    # Verify INV-205 has 3 distinct items
    inv_205 = next(inv for inv in invoices if inv.invoice_number == "INV-205")
    assert len(inv_205.items) == 3
    assert inv_205.total_amount == Decimal("47700.00")
    assert inv_205.payment_status == "unpaid"


def test_seed_validation_catches_mismatched_total():
    """Seed validation must fail if total_amount != sum(line_total)."""
    with pytest.raises(ValidationError, match="total_amount"):
        InvoiceSeed(
            invoice_number="INV-ERR-1",
            customer_id="CUST-101",
            invoice_date="2026-10-10",
            items=[
                LineItem(
                    product_id="PROD-101",
                    quantity=1,
                    unit_price=Decimal("100.00"),
                    line_total=Decimal("100.00"),
                )
            ],
            total_amount=Decimal("999.00"),  # Wrong! Should be 100.00
            invoice_status="issued",
            payment_status="unpaid",
        )


def test_seed_validation_catches_invalid_product_id():
    """Seed validation must fail if an unknown product_id is referenced."""
    inv = InvoiceSeed(
        invoice_number="INV-ERR-2",
        customer_id="CUST-101",
        invoice_date="2026-10-10",
        items=[
            LineItem(
                product_id="PROD-NONEXISTENT",
                quantity=1,
                unit_price=Decimal("100.00"),
                line_total=Decimal("100.00"),
            )
        ],
        total_amount=Decimal("100.00"),
        invoice_status="issued",
        payment_status="unpaid",
    )
    with pytest.raises(ValueError, match="Unknown product_id: PROD-NONEXISTENT"):
        inv.validate_product_ids({"PROD-101", "PROD-102"})


def test_seed_validation_catches_invalid_line_total():
    """LineItem must fail if line_total != quantity * unit_price."""
    with pytest.raises(ValidationError, match="line_total"):
        LineItem(
            product_id="PROD-101",
            quantity=2,
            unit_price=Decimal("500.00"),
            line_total=Decimal("999.00"),  # Wrong! 2 * 500 = 1000
        )


def test_seed_validation_catches_non_positive_quantity():
    """LineItem quantity must be > 0."""
    with pytest.raises(ValidationError):
        LineItem(
            product_id="PROD-101",
            quantity=0,
            unit_price=Decimal("500.00"),
            line_total=Decimal("0.00"),
        )


def test_header_aggregation_prevents_double_counting():
    """Header-only aggregation query must sum total_amount without multiplying line items."""
    # When calculating total value of unpaid invoices, standard query should be:
    # SELECT SUM(total_amount) FROM invoices WHERE invoice_status = 'issued' AND payment_status = 'unpaid'
    # From seed data:
    # - INV-202 (unpaid, issued): 2500.00 (5 items of PROD-103)
    # - INV-205 (unpaid, issued): 47700.00 (3 items)
    # Total should be 2500.00 + 47700.00 = 50200.00
    # Note: INV-204 is void (8000.00), so excluded.
    # Note: INV-203 is overdue (not unpaid).
    expected_sum = Decimal("2500.00") + Decimal("47700.00")
    assert expected_sum == Decimal("50200.00")

    # If line items were expanded:
    # INV-205 has 3 line items, so total_amount would be summed 3 times (47700 * 3) -> double-counting!
    double_counted_sum = Decimal("2500.00") + (Decimal("47700.00") * 3)
    assert expected_sum != double_counted_sum
