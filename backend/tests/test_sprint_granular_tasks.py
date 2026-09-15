"""Tests for granular sprint task tracking and deliverable linkage."""
import pytest
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator


@pytest.fixture
def temp_setup(tmp_path):
    db_file = tmp_path / "test_sprint_granular.db"
    store = StateStore(db_path=str(db_file))
    pm = ProjectManager(store=store)
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    p = pm.register_project("proj_sprint", "Sprint Project", str(ws_dir), auto_pilot=True)
    runner = AgentRunner(use_mock=True, store=store)
    orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
    return store, pm, orch, p


@pytest.mark.asyncio
async def test_sprint_tasks_linked_and_retrievable(temp_setup):
    store, pm, orch, project = temp_setup

    res = await orch.execute_pm_directive("proj_sprint", "Build authentication page and API")
    assert res["status"] == "COMPLETED"
    sprint_id = res["sprint_id"]

    # Verify tasks are linked to sprint_id
    tasks = store.get_sprint_tasks(sprint_id)
    assert len(tasks) >= 4  # Designer, FrontendDev, BackendDev, QATester
    roles = {t.assigned_to for t in tasks}
    assert "Designer" in roles
    assert "FrontendDev" in roles
    assert "BackendDev" in roles
    assert "QATester" in roles

    for t in tasks:
        assert t.sprint_id == sprint_id
        assert t.status.value == "DONE"
        assert t.result_output is not None
        assert len(t.result_output) > 0
