"""skills/invoice.py — InvoiceSkill prompt rules and JSONB query instructions."""


class InvoiceSkill:
    """Specialized skill providing invoice-domain rules for query generation."""

    NAME = "InvoiceSkill"

    @staticmethod
    def get_prompt_rules() -> str:
        """Returns strict SQL generation rules for invoice and billing queries."""
        return """
INVOICE DOMAIN RULES (CRITICAL - YOU MUST FOLLOW THESE):

1. VOID INVOICE EXCLUSION:
   Unless the user explicitly asks for 'void' or 'voided' invoices, ALWAYS exclude void invoices:
   WHERE i.invoice_status = :invoice_status (with parameter invoice_status = 'issued')
   or WHERE invoice_status = :invoice_status.

2. HEADER-ONLY AGGREGATION RULE (PREVENTS DOUBLE COUNTING):
   When querying invoice counts, invoice-level totals (SUM(total_amount)), averages, statuses,
   or dates WITHOUT requesting individual line-item product details, query the `invoices` table directly.
   NEVER expand `jsonb_array_elements(items)` for invoice-level sums or counts, because expanding
   line items duplicates invoice header rows and multiplies totals by the number of line items!

3. CANONICAL JSONB LINE-ITEM EXPANSION PATTERN:
   When querying products, quantities, unit prices, or line totals inside an invoice,
   ALWAYS use this exact CROSS JOIN LATERAL pattern with explicit `AS item(value)` aliasing:

   SELECT
       p.product_id,
       p.name AS product_name,
       CAST(item.value ->> 'quantity' AS INTEGER) AS quantity,
       CAST(item.value ->> 'unit_price' AS NUMERIC) AS unit_price,
       CAST(item.value ->> 'line_total' AS NUMERIC) AS line_total
   FROM invoices AS i
   CROSS JOIN LATERAL jsonb_array_elements(i.items) AS item(value)
   JOIN products AS p ON p.product_id = (item.value ->> 'product_id')
   WHERE i.invoice_number = :invoice_number
   LIMIT 100

4. TYPE CAST RULE:
   ALWAYS use `CAST(x AS NUMERIC)` or `CAST(x AS INTEGER)` or `CAST(x AS DATE)`.
   NEVER use PostgreSQL double-colon syntax (e.g. `::numeric` or `::text`), because the `:`
   character is strictly reserved for SQLAlchemy named bind parameters (`:param_name`).

5. DATE CALCULATION FOR "LAST MONTH":
   "Last month" means the previous calendar month.
   In PostgreSQL, use:
   WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
     AND invoice_date < DATE_TRUNC('month', CURRENT_DATE)
   Or bind specific start and end dates (:start_date, :end_date) when known.
""".strip()
