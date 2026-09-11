import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_api_projects_lifecycle(tmp_path):
    client = TestClient(app)
    
    # List projects
    res = client.get("/api/projects")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    
    workspace = tmp_path / "alpha"
    workspace.mkdir(parents=True, exist_ok=True)

    # Register Project Alpha
    res = client.post("/api/projects", json={
        "project_id": "alpha",
        "name": "Alpha App",
        "workspace_path": str(workspace),
        "auto_pilot": False
    })
    assert res.status_code == 200
    assert res.json()["project_id"] == "alpha"
    
    # Get project detail
    res = client.get("/api/projects/alpha")
    assert res.status_code == 200
    assert res.json()["name"] == "Alpha App"

    # Get agents list
    res = client.get("/api/projects/alpha/agents")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) >= 4
    assert any(a["role"] == "TechLead" for a in agents)
