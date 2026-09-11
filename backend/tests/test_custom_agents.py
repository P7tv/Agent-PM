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
