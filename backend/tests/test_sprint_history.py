import pytest
import os
import tempfile
import time
from app.models.schemas import SprintRecord
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator

def test_sprint_record_schema():
    rec = SprintRecord(
        sprint_id="sp-1",
        project_id="p-1",
        directive="Add dark mode",
        status="COMPLETED",
        total_tokens=1200,
        backend_used="cli",
        started_at=time.time(),
        completed_at=time.time() + 10,
        tasks_count=4,
        release_summary="Dark mode done"
    )
    assert rec.sprint_id == "sp-1"
    assert rec.total_tokens == 1200

def test_state_store_sprint_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        rec = SprintRecord(
            sprint_id="sp-1",
            project_id="p-1",
            directive="Build UI",
            status="RUNNING",
            started_at=time.time()
        )
        store.record_sprint(rec)
        sprints = store.get_sprints("p-1")
        assert len(sprints) == 1
        assert sprints[0].status == "RUNNING"
        
        store.update_sprint("sp-1", status="COMPLETED", total_tokens=500, release_summary="Done")
        sprints = store.get_sprints("p-1")
        assert sprints[0].status == "COMPLETED"
        assert sprints[0].total_tokens == 500
        assert sprints[0].release_summary == "Done"

@pytest.mark.asyncio
async def test_orchestrator_creates_sprint_record():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-sp", "Sprint Proj", tmpdir, auto_pilot=True)
        runner = AgentRunner(use_mock=True)
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        
        res = await orch.execute_pm_directive("proj-sp", "Add search feature")
        assert res["status"] == "COMPLETED"
        
        sprints = store.get_sprints("proj-sp")
        assert len(sprints) == 1
        assert sprints[0].directive == "Add search feature"
        assert sprints[0].status == "COMPLETED"
        assert sprints[0].tasks_count >= 1
