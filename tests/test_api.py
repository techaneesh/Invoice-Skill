"""test_api.py — Tests for /health and /api/chat endpoints."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from models import RouteDecision, GeneratedSQL

client = TestClient(app)


def test_health_endpoint_healthy():
    """Verify /health returns 200 when database connection succeeds."""
    with patch("main.check_db_connection", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["app_status"] == "healthy"
        assert data["db_status"] == "connected"


def test_health_endpoint_db_unavailable():
    """Verify /health returns 503 when database connection fails."""
    with patch("main.check_db_connection", return_value=False):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["app_status"] == "healthy"
        assert data["db_status"] == "unavailable"
        assert "error" in data


def test_chat_endpoint_empty_message_rejected():
    """FastAPI must reject empty message with 422 Unprocessable Entity."""
    response = client.post("/api/chat", json={"message": "", "session_id": "test"})
    assert response.status_code == 422


def test_chat_endpoint_success_structure():
    """Test full chat endpoint pipeline and response serialization."""
    mock_rows = [
        {
            "invoice_number": "INV-205",
            "invoice_date": "2026-10-10",
            "total_amount": "47700.00",
            "invoice_status": "issued",
            "payment_status": "unpaid",
        }
    ]

    with patch("agent.route_intent", return_value=RouteDecision(capability="InvoiceSkill")), \
         patch("agent.generate_and_execute", return_value=(mock_rows, "SELECT ...")), \
         patch("agent.synthesize_answer", return_value="The latest invoice for CUST-101 is INV-205 for ₹47,700.00."):

        response = client.post(
            "/api/chat",
            json={"message": "Show the latest invoice for customer CUST-101", "session_id": "demo"},
        )

        assert response.status_code == 200
        res = response.json()
        assert "request_id" in res
        assert res["status"] == "success"
        assert res["capability_used"] == "InvoiceSkill"
        assert "INV-205" in res["answer"]
        assert len(res["data"]) == 1
        # Crucial: Decimal serialization must be string "47700.00", not float 47700.0
        assert res["data"][0]["total_amount"] == "47700.00"
        assert isinstance(res["data"][0]["total_amount"], str)
        assert res["error"] is None


def test_chat_endpoint_clarification_required():
    """Test clarification response."""
    with patch(
        "agent.route_intent",
        return_value=RouteDecision(
            capability="clarification_required",
            clarification_question="Which customer are you looking for?",
        ),
    ):
        response = client.post(
            "/api/chat",
            json={"message": "Show details", "session_id": "demo"},
        )
        assert response.status_code == 200
        res = response.json()
        assert res["status"] == "clarification_required"
        assert "Which customer" in res["answer"]


def test_chat_endpoint_rejected():
    """Test rejected modifying operation."""
    response = client.post(
        "/api/chat",
        json={"message": "DROP TABLE customers", "session_id": "demo"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "error"
    assert "not permitted" in res["answer"] or "rejected" in str(res["error"])
