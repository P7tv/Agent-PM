import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager

def test_project_manager_isolation_and_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store, max_projects=2)
        
        dir_a = os.path.join(tmpdir, "proj_a")
        dir_b = os.path.join(tmpdir, "proj_b")
        dir_c = os.path.join(tmpdir, "proj_c")
        os.makedirs(dir_a)
        os.makedirs(dir_b)
        os.makedirs(dir_c)
        
        p1 = pm.register_project("proj-a", "Project A", dir_a)
        p2 = pm.register_project("proj-b", "Project B", dir_b)
        assert len(pm.get_active_projects()) == 2
        
        # Max limit exceeded should raise ValueError
        with pytest.raises(ValueError, match="Maximum active projects"):
            pm.register_project("proj-c", "Project C", dir_c)
            
        # Verify workspace directory resolution
        assert pm.get_project_workspace("proj-a") == dir_a

def test_project_manager_unlimited_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)  # default max_projects=None
        
        for i in range(5):
            d = os.path.join(tmpdir, f"proj_{i}")
            os.makedirs(d)
            pm.register_project(f"proj-{i}", f"Project {i}", d)
            
        assert len(pm.get_active_projects()) == 5

