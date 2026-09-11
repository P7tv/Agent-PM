import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_orchestrator_pipeline_auto():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-1", "Project 1", tmpdir, auto_pilot=True)
        runner = AgentRunner(use_mock=True)
        
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        result = await orch.execute_pm_directive("proj-1", "Build landing page")
        
        assert result["status"] == "COMPLETED"
        tasks = store.get_tasks("proj-1")
        assert len(tasks) > 0

@pytest.mark.asyncio
async def test_orchestrator_self_healing_qa_retry():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-2", "Project 2", tmpdir, auto_pilot=True)
        runner = AgentRunner(use_mock=True)
        
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        events = []
        async def on_event(ev_type, data):
            events.append(ev_type)
            
        result = await orch.execute_pm_directive("proj-2", "Refactor auth", event_callback=on_event)
        assert result["status"] == "COMPLETED"
        assert "AGENT_THOUGHT_DELTA" in events

@pytest.mark.asyncio
async def test_orchestrator_parallel_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-parallel", "Parallel Proj", tmpdir, auto_pilot=True)
        
        start_times = {}
        runner = AgentRunner(use_mock=True)
        orig_dispatch = runner.dispatch_agent_task
        
        async def tracking_dispatch(*args, **kwargs):
            role = kwargs.get("role") or (args[1] if len(args) > 1 else None)
            import time
            start_times[role] = time.time()
            return await orig_dispatch(*args, **kwargs)
            
        runner.dispatch_agent_task = tracking_dispatch
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        result = await orch.execute_pm_directive("proj-parallel", "Build fullstack feature")
        
        assert result["status"] == "COMPLETED"
        assert "Designer" in start_times and "BackendDev" in start_times
        # Designer and BackendDev should start within 40ms of each other (parallel)
        assert abs(start_times["Designer"] - start_times["BackendDev"]) < 0.04

