import os
from typing import List, Optional
from app.services.state_store import StateStore
from app.models.schemas import Project, AgentRole

DEFAULT_ROLES = [
    AgentRole.ARCHITECT.value,
    AgentRole.DESIGNER.value,
    AgentRole.FRONTEND_DEV.value,
    AgentRole.BACKEND_DEV.value,
    AgentRole.QA_TESTER.value,
    AgentRole.REVIEWER.value,
    AgentRole.DOC_WRITER.value,
]

class ProjectManager:
    def __init__(self, store: StateStore, max_projects: int = 2):
        self.store = store
        self.max_projects = max_projects

    def register_project(self, project_id: str, name: str, workspace_path: str, auto_pilot: bool = False) -> Project:
        resolved_path = os.path.abspath(workspace_path)
        if not os.path.exists(resolved_path):
            os.makedirs(resolved_path, exist_ok=True)
            
        existing = self.store.get_project(project_id)
        if not existing:
            current_projects = self.store.list_projects()
            if len(current_projects) >= self.max_projects:
                raise ValueError(f"Maximum active projects limit ({self.max_projects}) reached.")
        
        proj = self.store.create_project(project_id, name, resolved_path, auto_pilot)
        
        # Initialize default agent states
        for role in DEFAULT_ROLES:
            self.store.set_agent_status(project_id, role, "IDLE", "Ready for PM directives")
            
        return proj

    def get_active_projects(self) -> List[Project]:
        return self.store.list_projects()

    def get_project(self, project_id: str) -> Optional[Project]:
        return self.store.get_project(project_id)

    def get_project_workspace(self, project_id: str) -> str:
        proj = self.store.get_project(project_id)
        if not proj:
            raise KeyError(f"Project {project_id} not found")
        return proj.workspace_path
