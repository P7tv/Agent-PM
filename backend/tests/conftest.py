"""
Shared test fixtures for isolating tests from production state.
"""
import pytest
import os
import tempfile
from app.services.state_store import StateStore


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """
    Automatically replace the production StateStore in routes.py
    with a temporary database for every test, preventing test pollution.
    """
    tmpdir = tempfile.mkdtemp()
    test_db_path = os.path.join(tmpdir, "test_state.db")
    test_store = StateStore(db_path=test_db_path)

    # Patch the global singletons in routes module
    import app.api.routes as routes_module
    from app.services.project_manager import ProjectManager
    from app.services.agent_runner import AgentRunner
    from app.services.orchestrator import Orchestrator

    test_pm = ProjectManager(store=test_store)
    test_runner = AgentRunner(use_mock=True)
    test_orchestrator = Orchestrator(store=test_store, project_manager=test_pm, agent_runner=test_runner)

    monkeypatch.setattr(routes_module, "store", test_store)
    monkeypatch.setattr(routes_module, "pm", test_pm)
    monkeypatch.setattr(routes_module, "runner", test_runner)
    monkeypatch.setattr(routes_module, "orchestrator", test_orchestrator)

    yield test_store

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
