from fastapi.testclient import TestClient
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)

@patch("app.main.get_db_pool")
@patch("app.main.trigger_replan", new_callable=AsyncMock)
def test_ingest_telemetry_nominal(mock_trigger, mock_db_pool):
    payload = {
        "uav_id": 1,
        "current_node_id": 2,
        "target_node_id": 5,
        "delay_ms": 100,
        "deviation_m": 5.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "has_threat_notification": False
    }
    
    response = client.post("/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["replan_triggered"] == False
    assert data["reason"] == "Nominal flight parameters"
    mock_trigger.assert_not_called()

@patch("app.main.get_db_pool")
@patch("app.main.trigger_replan", new_callable=AsyncMock)
def test_ingest_telemetry_high_delay(mock_trigger, mock_db_pool):
    # Mock db connection execute method
    mock_conn = AsyncMock()
    mock_pool = AsyncMock()
    mock_pool.execute = mock_conn
    mock_db_pool.return_value = mock_pool

    payload = {
        "uav_id": 1,
        "current_node_id": 2,
        "target_node_id": 5,
        "delay_ms": 250,
        "deviation_m": 5.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "has_threat_notification": False
    }
    
    response = client.post("/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["replan_triggered"] == True
    assert "exceeded 200ms" in data["reason"]
    mock_trigger.assert_called_once()
