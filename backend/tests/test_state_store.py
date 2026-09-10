import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.models.schemas import Project, AgentState, TaskItem, TaskStatus, AgentStatus

def test_state_store_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = StateStore(db_path)
        
        # Create Project
        proj = store.create_project(project_id="proj-a", name="Project Alpha", workspace_path=tmpdir)
        assert proj.project_id == "proj-a"
        assert proj.name == "Project Alpha"
        
        # Add Task
        task = store.create_task(project_id="proj-a", title="Setup DB", assigned_to="BackendDev")
        assert task.title == "Setup DB"
        assert task.status == TaskStatus.TODO
        
        # Update Task
        updated = store.update_task_status(task.task_id, "IN_PROGRESS")
        assert updated.status == TaskStatus.IN_PROGRESS
        
        # Update Agent State
        store.set_agent_status(project_id="proj-a", role="BackendDev", status="THINKING", thought="Designing schema")
        agent_state = store.get_agent_status("proj-a", "BackendDev")
        assert agent_state.status == AgentStatus.THINKING
        assert agent_state.thought == "Designing schema"
