import pytest
import os
import tempfile
import time
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import SprintRecord

def test_export_sprint_release_notes(tmp_path, isolated_db):
    client = TestClient(app)
    pid = "test-export-proj"
    workspace = tmp_path / "export_ws"
    workspace.mkdir()
    
    # Register project via API
    res = client.post("/api/projects", json={
        "project_id": pid,
        "name": "Export Proj",
        "workspace_path": str(workspace),
        "auto_pilot": False
    })
    assert res.status_code == 200
    
    # Record sprint in isolated_db
    sprint = SprintRecord(
        sprint_id="sp-export-1",
        project_id=pid,
        directive="Implement dark mode toggle",
        status="COMPLETED",
        total_tokens=1500,
        backend_used="cli",
        started_at=time.time() - 30,
        completed_at=time.time(),
        tasks_count=3,
        release_summary="Added dark mode styling and toggle button."
    )
    isolated_db.record_sprint(sprint)
    
    # Test export endpoint
    res = client.get(f"/api/projects/{pid}/sprints/{sprint.sprint_id}/export")
    assert res.status_code == 200
    assert "text/markdown" in res.headers.get("content-type", "")
    content = res.text
    assert "Sprint Release Notes" in content
    assert sprint.directive in content
    assert "COMPLETED" in content
    assert "1,500 tokens" in content
    assert "Added dark mode styling" in content

def test_export_git_patch(tmp_path):
    client = TestClient(app)
    pid = "test-patch-proj"
    workspace = tmp_path / "patch_ws"
    workspace.mkdir()
    
    # Register project
    res = client.post("/api/projects", json={
        "project_id": pid,
        "name": "Patch Proj",
        "workspace_path": str(workspace),
        "auto_pilot": False
    })
    assert res.status_code == 200
    
    # Init git repo
    res_init = client.post(f"/api/projects/{pid}/git/init")
    assert res_init.status_code == 200
    
    # Fetch patch
    res = client.get(f"/api/projects/{pid}/git/patch")
    assert res.status_code == 200
    assert "attachment" in res.headers.get("content-disposition", "")

def test_global_queue_endpoints(tmp_path, isolated_db):
    client = TestClient(app)
    pid = "test-queue-proj"
    workspace = tmp_path / "queue_ws"
    workspace.mkdir()
    
    # Register project
    client.post("/api/projects", json={
        "project_id": pid,
        "name": "Queue Proj",
        "workspace_path": str(workspace),
        "auto_pilot": False
    })
    
    # Enqueue directive directly into isolated_db
    item = isolated_db.enqueue_directive(pid, "Test queue task 1")
    
    # Query global queue
    res = client.get("/api/queue/all")
    assert res.status_code == 200
    data = res.json()
    assert any(it["queue_id"] == item.queue_id for it in data)
    
    # Cancel item
    del_res = client.delete(f"/api/queue/{item.queue_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "CANCELLED"
