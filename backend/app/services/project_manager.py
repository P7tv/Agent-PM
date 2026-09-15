import os
from typing import List, Optional
from app.services.state_store import StateStore
from app.models.schemas import Project, AgentRole

DEFAULT_ROLES = [
    AgentRole.TECH_LEAD.value,
    AgentRole.ARCHITECT.value,
    AgentRole.DESIGNER.value,
    AgentRole.FRONTEND_DEV.value,
    AgentRole.BACKEND_DEV.value,
    AgentRole.QA_TESTER.value,
    AgentRole.REVIEWER.value,
    AgentRole.DOC_WRITER.value,
]

from app.services.workspace_inspector import WorkspaceInspector

class ProjectManager:
    def __init__(self, store: StateStore, max_projects: Optional[int] = None):
        self.store = store
        self.max_projects = max_projects
        self.inspector = WorkspaceInspector()

    def register_project(self, project_id: str, name: str, workspace_path: str, auto_pilot: bool = False) -> Project:
        # 1. Guardrail Validation
        valid, msg, meta = self.inspector.validate_guardrails(workspace_path)
        if not valid:
            raise ValueError(f"Guardrail Check Failed: {msg}")

        resolved_path = meta["path"]
            
        existing = self.store.get_project(project_id)
        if not existing:
            current_projects = self.store.list_projects()
            if self.max_projects is not None and len(current_projects) >= self.max_projects:
                raise ValueError(f"Maximum active projects limit ({self.max_projects}) reached.")
        
        proj_name = name or meta.get("suggested_name") or "Project"
        proj = self.store.create_project(project_id, proj_name, resolved_path, auto_pilot, metadata=meta)
        
        # 2. Dynamic Subagent Tailoring based on analyzed codebase
        tailored_agents = self.inspector.generate_tailored_roster(meta)
        for agent in tailored_agents:
            self.store.set_agent_status(
                project_id=project_id,
                role=agent["role"],
                status="IDLE",
                thought=f"Specialized for {meta.get('stack_type')}: {agent['description']}",
                skill_name=agent.get("skill_name"),
                skill_tier=agent.get("skill_tier", "stock"),
                skill_title=agent.get("title")
            )
            
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
