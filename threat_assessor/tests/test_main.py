from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200

@patch("app.main.get_db_pool")
def test_assess_threats(mock_db_pool):
    mock_conn = AsyncMock()
    # Mocking db fetch
    async def mock_fetch(query, geojson):
        if "ST_DWithin" in query:
            return [{"probability": 0.5, "criticality": 0.8}]
        return []

    mock_conn.fetch.side_effect = mock_fetch
    mock_db_pool.return_value = mock_conn

    payload = {
        "segments": [{"id": 1, "geometry_geojson": "{}"}]
    }

    response = client.post("/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["segment_id"] == 1
    assert data["results"][0]["p_att"] == 0.4  # 1 - (1 - 0.5 * 0.8)
