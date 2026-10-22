"""
Integration tests for FastAPI endpoints in TCWC-25 Calculator.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "TCWC-25" in data["service"]


def test_get_products_endpoint():
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 5
    ids = [p["id"] for p in products]
    assert "equity_mf" in ids
    assert "fixed_deposit" in ids
    assert "ppf" in ids
    assert "debt_mf" in ids
    assert "hybrid_mf" in ids


def test_calculate_target_driven_success():
    payload = {
        "current_age": 28,
        "future_age": 45,
        "current_expenditure": 600000,
        "mode": "target_driven",
        "product_id": "equity_mf",
        "inflation_rate": 0.055
    }
    response = client.post("/api/v1/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tenure_years"] == 17
    assert data["product_id"] == "equity_mf"
    assert data["required_lumpsum"] is not None
    assert data["required_lumpsum"]["raw"] > 0
    assert data["fine_print_disclaimer"] is not None


def test_calculate_projection_success():
    payload = {
        "current_age": 30,
        "future_age": 40,
        "current_expenditure": 1200000,
        "mode": "projection",
        "existing_lumpsum": 500000,
        "product_id": "hybrid_mf",
        "inflation_rate": 0.06
    }
    response = client.post("/api/v1/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tenure_years"] == 10
    assert data["projected_nominal_corpus"] is not None
    assert data["goal_gap"] is not None
    assert data["real_purchasing_power"] is not None


def test_calculate_validation_failure_equal_age():
    payload = {
        "current_age": 35,
        "future_age": 35,
        "current_expenditure": 500000
    }
    response = client.post("/api/v1/calculate", json=payload)
    assert response.status_code == 422
    assert "strictly greater than current age" in response.text
