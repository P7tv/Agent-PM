import pytest
import os
import tempfile
from app.models.schemas import QueueItem
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator
from app.services.sprint_queue import SprintQueue

def test_queue_item_schema():
    item = QueueItem(project_id="p1", directive="Task 1", position=0)
    assert item.status == "QUEUED"
    assert item.directive == "Task 1"

def test_state_store_queue_ops():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        item1 = store.enqueue_directive("p1", "Directive 1")
        item2 = store.enqueue_directive("p1", "Directive 2")
        
        q = store.get_queue("p1")
        assert len(q) == 2
        assert q[0].directive == "Directive 1"
        assert q[1].directive == "Directive 2"
        
        store.cancel_queue_item(item1.queue_id)
        q2 = store.get_queue("p1")
        assert len(q2) == 1
        assert q2[0].directive == "Directive 2"

@pytest.mark.asyncio
async def test_sprint_queue_drains_sequentially():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("pq", "Queue Proj", tmpdir, auto_pilot=True)
        runner = AgentRunner(use_mock=True)
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        
        executed = []
        orig_exec = orch.execute_pm_directive
        async def mock_exec(project_id, directive, **kw):
            executed.append(directive)
            return await orig_exec(project_id, directive, **kw)
        orch.execute_pm_directive = mock_exec
        
        sq = SprintQueue(store=store, orchestrator=orch)
        sq.enqueue("pq", "First directive")
        sq.enqueue("pq", "Second directive")
        
        # Wait for worker task to drain
        await sq._workers["pq"]
        
        assert executed == ["First directive", "Second directive"]
        assert len(store.get_queue("pq")) == 0

def test_sprint_queue_api_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    
    # Create project
    res = client.post("/api/projects", json={
        "project_id": "test-q-api",
        "name": "Queue API Test",
        "workspace_path": "/tmp",
        "auto_pilot": True
    })
    assert res.status_code == 200
    
    # Enqueue directive
    res = client.post("/api/projects/test-q-api/queue", json={"directive": "Deploy to prod"})
    assert res.status_code == 200
    data = res.json()
    queue_id = data["queue_id"]
    assert data["directive"] == "Deploy to prod"
    
    # Get queue
    res = client.get("/api/projects/test-q-api/queue")
    assert res.status_code == 200
    
    # Clean up project
    client.delete("/api/projects/test-q-api")

