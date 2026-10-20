"""test_routing.py — Tests for InvoiceSkill vs GeneralQuery routing."""

from unittest.mock import patch
from agent import route_intent
from models import RouteDecision


def test_destructive_prompts_rejected_immediately():
    """Destructive or SQL modification attempts must be rejected."""
    decision = route_intent("DROP TABLE customers;")
    assert decision.capability == "rejected"

    decision2 = route_intent("DELETE FROM invoices WHERE id = 1;")
    assert decision2.capability == "rejected"

    decision3 = route_intent("TRUNCATE TABLE products;")
    assert decision3.capability == "rejected"


def test_invoice_skill_routing():
    """Invoice, billing, payment status, and order item questions route to InvoiceSkill."""
    mock_resp = {"capability": "InvoiceSkill", "clarification_question": None}

    with patch("agent.call_llm", return_value=mock_resp):
        decision = route_intent("Show all unpaid invoices.")
        assert decision.capability == "InvoiceSkill"

        decision = route_intent("Show invoice INV-205.")
        assert decision.capability == "InvoiceSkill"

        decision = route_intent("Which products are included in invoice INV-205?")
        assert decision.capability == "InvoiceSkill"


def test_general_query_routing():
    """Standalone product catalog and customer lookups route to GeneralQuery."""
    mock_resp = {"capability": "GeneralQuery", "clarification_question": None}

    with patch("agent.call_llm", return_value=mock_resp):
        decision = route_intent("Show all products in the electronics category.")
        assert decision.capability == "GeneralQuery"

        decision = route_intent("Find customer CUST-101's email.")
        assert decision.capability == "GeneralQuery"


def test_clarification_required_routing():
    """Ambiguous or context-free questions require clarification."""
    mock_resp = {
        "capability": "clarification_required",
        "clarification_question": "Which invoice or customer are you referring to?",
    }

    with patch("agent.call_llm", return_value=mock_resp):
        decision = route_intent("Show the latest one.")
        assert decision.capability == "clarification_required"
        assert decision.clarification_question is not None
