import pytest
import time
from app.services.state_store import StateStore
from app.models.schemas import AgentStatus, CustomAgentCreateRequest, AutoGenerateRosterRequest

def test_add_and_delete_custom_agent(tmp_path):
    db_file = str(tmp_path / "test_state.db")
    store = StateStore(db_path=db_file)
    store.create_project("proj-1", "Test App", "/test/path")
    
    # 1. Add custom agent
    agent = store.add_agent(
        project_id="proj-1",
        role="GamePhysicsDev",
        title="Physics & Vehicle Dynamics Engineer",
        description="Simulates aerodynamic forces and tire grip.",
        skill_name="systematic-debugger",
        skill_tier="stock"
    )
    assert agent.role == "GamePhysicsDev"
    assert agent.skill_title == "Physics & Vehicle Dynamics Engineer"
    assert "aerodynamic forces" in agent.thought
    assert agent.skill_name == "systematic-debugger"
    
    # 2. Retrieve all agents
    agents = store.get_all_agent_states("proj-1")
    assert any(a.role == "GamePhysicsDev" for a in agents)
    
    # 3. Delete custom agent
    deleted = store.delete_agent("proj-1", "GamePhysicsDev")
    assert deleted is True
    assert not any(a.role == "GamePhysicsDev" for a in store.get_all_agent_states("proj-1"))
    
    # 4. TechLead cannot be deleted
    store.set_agent_status("proj-1", "TechLead", "IDLE")
    cannot_delete = store.delete_agent("proj-1", "TechLead")
    assert cannot_delete is False
    assert any(a.role == "TechLead" for a in store.get_all_agent_states("proj-1"))

def test_auto_generate_roster_heuristics(tmp_path):
    from app.services.tech_lead_service import TechLeadService
    from app.services.project_manager import ProjectManager
    from app.services.state_store import StateStore
    
    db_file = str(tmp_path / "test_state.db")
    store = StateStore(db_path=db_file)
    pm = ProjectManager(store=store)
    tls = TechLeadService(store=store, pm=pm)
    
    # Create project with 3D game metadata
    meta = {
        "path": "/test/f1-game",
        "suggested_name": "F1 3D Simulation",
        "stack_type": "3D WebGL (Three.js + Vite)",
        "frameworks": ["three", "vite"],
        "purpose_summary": "Formula 1 Racing Game simulation with aerodynamic physics and tracks."
    }
    store.create_project("proj-game", "F1 3D Simulation", "/test/f1-game", metadata=meta)
    store.set_agent_status("proj-game", "TechLead", "IDLE")
    # Pre-existing generic agent
    store.set_agent_status("proj-game", "Designer", "IDLE")
    
    result = tls.auto_generate_roster("proj-game", replace_existing=True)
    assert result["status"] == "SUCCESS"
    agents = result["agents"]
    roles = [a["role"] for a in agents]
    assert "TechLead" in roles
    # Designer should be replaced
    assert "Designer" not in roles
    # Verify specialized roles generated
    assert any("Physics" in (a.get("skill_title") or a.get("role") or "") or "Three" in (a.get("skill_title") or a.get("role") or "") or "Game" in (a.get("skill_title") or a.get("role") or "") for a in agents)

@pytest.mark.asyncio
async def test_agent_runner_custom_role_persona(tmp_path):
    from app.services.agent_runner import AgentRunner
    
    db_file = str(tmp_path / "test_state.db")
    store = StateStore(db_path=db_file)
    store.create_project("proj-c", "Custom App", "/test/custom")
    store.add_agent(
        "proj-c",
        role="CryptoAuditor",
        title="Smart Contract Security Auditor",
        description="Audits EVM bytecode and gas usage."
    )
    
    runner = AgentRunner(use_mock=True, store=store)
    events = []
    async def cb(ev, data):
        events.append((ev, data))
        
    res = await runner.dispatch_agent_task(
        project_id="proj-c",
        role="CryptoAuditor",
        prompt="Audit the staking contract for reentrancy bugs.",
        workspace_path="/test/custom",
        event_callback=cb
    )
    assert res["role"] == "CryptoAuditor"
    assert res["status"] == "SUCCESS"
    # Verify persona was reflected in events
    deltas = [d.get("thought", "") for ev, d in events if ev == "AGENT_THOUGHT_DELTA"]
    assert any("EVM" in d or "gas usage" in d for d in deltas)

def test_custom_agent_api_endpoints(tmp_path, isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    
    workspace = tmp_path / "custom_ws"
    workspace.mkdir()
    
    # Register project
    res = client.post("/api/projects", json={
        "project_id": "api-proj",
        "name": "API Proj",
        "workspace_path": str(workspace)
    })
    assert res.status_code == 200
    
    # 1. Add custom agent
    res = client.post("/api/projects/api-proj/agents", json={
        "role": "PerformanceAuditor",
        "title": "Latency & Core Web Vitals Specialist",
        "description": "Profiles memory consumption and render bottleneck.",
        "skill_name": "performance-optimization"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "PerformanceAuditor"
    assert data["skill_title"] == "Latency & Core Web Vitals Specialist"
    
    # 2. Delete custom agent
    del_res = client.delete("/api/projects/api-proj/agents/PerformanceAuditor")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "DELETED"
    
    # 3. Cannot delete TechLead
    del_tl = client.delete("/api/projects/api-proj/agents/TechLead")
    assert del_tl.status_code == 400
    
    # 4. Auto-generate team
    gen_res = client.post("/api/projects/api-proj/agents/auto-generate", json={"replace_existing": True})
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert len(gen_data["agents"]) >= 3
    assert any(a["role"] == "TechLead" for a in gen_data["agents"])
