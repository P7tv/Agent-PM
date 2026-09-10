import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.models.schemas import AgentRole

def test_project_metadata_persistence_and_tech_lead():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = StateStore(db_path=db_path)
        pm = ProjectManager(store=store)
        
        # Create workspace with requirements.txt
        ws_dir = os.path.join(tmpdir, "ws")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write("fastapi\npytest\n")
            
        proj = pm.register_project("proj-test", "Test Proj", ws_dir)
        
        # Check metadata stored
        meta = store.get_project_metadata("proj-test")
        assert meta is not None
        assert "Python" in meta.get("stack_type", "")
        
        # Check TechLead agent registered
        agents = store.list_agents("proj-test")
        roles = [a.role for a in agents]
        assert "TechLead" in roles
        assert len(agents) == 8
