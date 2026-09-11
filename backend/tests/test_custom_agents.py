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
