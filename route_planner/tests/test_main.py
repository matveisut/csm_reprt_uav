from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import networkx as nx
from app.main import app

client = TestClient(app)

@patch("app.main.get_db_pool")
@patch("app.main.assess_threats_for_segments", new_callable=AsyncMock)
def test_plan_route(mock_assess, mock_db_pool):
    # Mock assess responses
    mock_assess.return_value = [{"segment_id": 1, "p_att": 0.1}]
    
    # Mock db pool and conn
    mock_conn = AsyncMock()
    
    async def mock_fetch(query):
        if "graph_nodes" in query:
            return [{"id": 1, "lon": 0.0, "lat": 0.0}, {"id": 2, "lon": 1.0, "lat": 1.0}]
        if "graph_edges" in query:
            return [{"id": 1, "source_node": 1, "target_node": 2, "base_time": 10.0, "r_link": 0.9, "geojson": "{}"}]
        return []
        
    mock_conn.fetch.side_effect = mock_fetch
    mock_db_pool.return_value = mock_conn

    payload = {
        "uav_id": 1,
        "source_node_id": 1,
        "target_node_id": 2,
        "alpha": 0.4,
        "beta": 0.3,
        "gamma": 0.3
    }
    
    response = client.post("/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["uav_id"] == 1
    assert data["path"] == [1, 2]
    assert data["estimated_time"] == 10.0
