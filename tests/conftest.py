"""conftest.py — Pytest fixtures and mock configurations."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def api_client():
    """Test client for FastAPI endpoints."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_llm_client(monkeypatch):
    """Fixture to mock call_llm for predictable test execution."""
    mock = MagicMock()
    monkeypatch.setattr("query_engine.call_llm", mock)
    monkeypatch.setattr("agent.call_llm", mock)
    return mock
