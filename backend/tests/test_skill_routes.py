import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
import tempfile
import os

@pytest.fixture
def client_with_project():
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy workspace
        ws_dir = os.path.join(tmpdir, "ws_app")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "package.json"), "w") as f:
            f.write('{"name": "test-web-app", "dependencies": {"react": "^18.0.0"}}')
        
        # Register project
        res = client.post("/api/projects", json={
            "project_id": "test-p1",
            "name": "Test Web App",
            "workspace_path": ws_dir
        })
        assert res.status_code == 200
        yield client, ws_dir

def test_get_global_skills(client_with_project):
    client, _ = client_with_project
    res = client.get("/api/skills")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    skill_names = [s["name"] for s in data]
    assert "backend-dev" in skill_names
    assert "tech-lead" in skill_names

def test_get_project_skills(client_with_project):
    client, _ = client_with_project
    res = client.get("/api/projects/test-p1/skills")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    # Check that each item has role and skill info
    roles = [s["role"] for s in data]
    assert "TechLead" in roles

def test_get_and_update_agent_skill(client_with_project):
    client, ws_dir = client_with_project
    # 1. Get skill for TechLead
    res = client.get("/api/projects/test-p1/skills/TechLead")
    assert res.status_code == 200
    skill_data = res.json()
    assert "instructions" in skill_data
    assert skill_data["tier"] == "stock"

    # 2. Update skill for TechLead (save project override)
    custom_markdown = """---
name: tech-lead
title: Custom PM Lead
description: Custom project rules
---
# Customized Tech Lead Playbook
Rule 1: Always verify PR before merging.
"""
    put_res = client.put("/api/projects/test-p1/skills/TechLead", json={"content": custom_markdown})
    assert put_res.status_code == 200
    updated_data = put_res.json()
    assert updated_data["status"] == "SUCCESS"

    # 3. Re-fetch: should now be tier="project"
    refetch_res = client.get("/api/projects/test-p1/skills/TechLead")
    assert refetch_res.status_code == 200
    refetched = refetch_res.json()
    assert refetched["tier"] == "project"
    assert "Customized Tech Lead Playbook" in refetched["instructions"]
