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
        # Designer and BackendDev should start almost concurrently (parallel vs sequential ~1s)
        assert abs(start_times["Designer"] - start_times["BackendDev"]) < 0.15

@pytest.mark.asyncio
async def test_orchestrator_abort_pipeline_at_runtime():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-abort", "Abort Proj", tmpdir, auto_pilot=True)
        
        runner = AgentRunner(use_mock=True)
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        
        orig_dispatch = runner.dispatch_agent_task
        async def aborting_dispatch(*args, **kwargs):
            role = kwargs.get("role") or (args[1] if len(args) > 1 else None)
            if role == "Designer":
                # Abort during parallel execution
                orch.abort_pipeline("proj-abort")
            return await orig_dispatch(*args, **kwargs)
            
        runner.dispatch_agent_task = aborting_dispatch
        result = await orch.execute_pm_directive("proj-abort", "Build quick feature")
        
        assert result["status"] == "ABORTED"
        sprints = store.get_sprints("proj-abort")
        assert len(sprints) == 1
        assert sprints[0].status == "FAILED"
        assert "aborted" in sprints[0].release_summary.lower()

@pytest.mark.asyncio
async def test_orchestrator_qa_self_healing_frontend_routing():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-fe-heal", "FE Heal Proj", tmpdir, auto_pilot=True)
        
        runner = AgentRunner(use_mock=True)
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        
        dispatched_roles = []
        qa_call_count = 0
        orig_dispatch = runner.dispatch_agent_task
        
        async def custom_dispatch(*args, **kwargs):
            nonlocal qa_call_count
            role = kwargs.get("role") or (args[1] if len(args) > 1 else None)
            dispatched_roles.append(role)
            if role == "QATester":
                qa_call_count += 1
                if qa_call_count == 1:
                    # Return a frontend-specific failure report
                    return {
                        "status": "SUCCESS",
                        "role": "QATester",
                        "response": "FAIL: Button UI styling and JSX component layout broken in frontend",
                        "tokens_used": 50,
                        "backend_used": "mock"
                    }
                else:
                    return {
                        "status": "SUCCESS",
                        "role": "QATester",
                        "response": "PASS: All tests pass",
                        "tokens_used": 50,
                        "backend_used": "mock"
                    }
            return await orig_dispatch(*args, **kwargs)
            
        runner.dispatch_agent_task = custom_dispatch
        result = await orch.execute_pm_directive("proj-fe-heal", "Fix button component")
        
        assert result["status"] == "COMPLETED"
        qa_index_1 = dispatched_roles.index("QATester")
        assert dispatched_roles[qa_index_1 + 1] == "FrontendDev"


