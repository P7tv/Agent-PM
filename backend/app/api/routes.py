from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator
from app.services.tech_lead_service import TechLeadService
from app.services.git_service import GitService
from app.services.skill_manager import SkillManager
from app.api.websocket_hub import hub
from app.models.schemas import DownloadSkillRequest, AssignSkillRequest

router = APIRouter(prefix="/api")

# Default database in project directory
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "state.db")
store = StateStore(db_path=db_path)
pm = ProjectManager(store=store)
runner = AgentRunner(use_mock=False)
orchestrator = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
tech_lead_svc = TechLeadService(store=store, pm=pm)
git_svc = GitService()
skill_manager = SkillManager()

class SkillUpdateRequest(BaseModel):
    content: str

class CreateProjectRequest(BaseModel):
    project_id: str
    name: str
    workspace_path: str
    auto_pilot: bool = False

class LeadChatRequest(BaseModel):
    message: str

class DirectiveRequest(BaseModel):
    directive: str

class ApprovalDecisionRequest(BaseModel):
    decision: str  # APPROVED / REJECTED

class WhisperRequest(BaseModel):
    role: str
    message: str

class ValidatePathRequest(BaseModel):
    path: str

@router.post("/projects/validate-path")
def validate_path(req: ValidatePathRequest):
    valid, msg, meta = pm.inspector.validate_guardrails(req.path)
    return {
        "valid": valid,
        "message": msg,
        "metadata": meta
    }

@router.get("/projects")
def get_projects():
    return store.list_projects()

@router.post("/projects")
def create_project(req: CreateProjectRequest):
    try:
        return pm.register_project(req.project_id, req.name, req.workspace_path, req.auto_pilot)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/projects/{project_id}")
def get_project(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    store.delete_project(project_id)
    await hub.broadcast("PROJECT_DELETED", {"project_id": project_id})
    return {"status": "DELETED", "project_id": project_id}

@router.get("/projects/{project_id}/agents")
def get_project_agents(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_all_agent_states(project_id)

@router.get("/projects/{project_id}/tasks")
def get_project_tasks(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_tasks(project_id)

@router.get("/projects/{project_id}/approvals")
def get_project_approvals(project_id: str):
    return store.get_pending_approvals(project_id)

@router.post("/projects/{project_id}/approvals/{request_id}")
async def resolve_approval(project_id: str, request_id: str, req: ApprovalDecisionRequest):
    store.resolve_approval(request_id, req.decision)
    # Signal the orchestrator to unblock the pipeline
    orchestrator.resolve_gate(request_id, req.decision)
    await hub.broadcast("DECISION_GATE_RESOLVED", {
        "project_id": project_id,
        "request_id": request_id,
        "decision": req.decision
    })
    return {"status": "RESOLVED", "decision": req.decision}

@router.post("/projects/{project_id}/whisper")
async def whisper_to_agent(project_id: str, req: WhisperRequest, bg: BackgroundTasks):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    async def run_whisper():
        store.set_agent_status(project_id, req.role, "THINKING", f"PM whispered: {req.message}")
        await hub.broadcast("AGENT_WHISPER_RECEIVED", {
            "project_id": project_id,
            "role": req.role,
            "message": req.message
        })
        await runner.dispatch_agent_task(
            project_id=project_id,
            role=req.role,
            prompt=f"PM Directive: {req.message}",
            workspace_path=p.workspace_path,
            event_callback=hub.broadcast
        )
        
    bg.add_task(run_whisper)
    return {"status": "WHISPER_SENT", "role": req.role}

@router.post("/projects/{project_id}/directive")
async def send_directive(project_id: str, req: DirectiveRequest, bg: BackgroundTasks):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    async def run_pipeline():
        await hub.broadcast("DIRECTIVE_STARTED", {"project_id": project_id, "directive": req.directive})
        await orchestrator.execute_pm_directive(
            project_id=project_id,
            directive=req.directive,
            event_callback=hub.broadcast
        )
        
    bg.add_task(run_pipeline)
    return {"status": "QUEUED", "project_id": project_id, "directive": req.directive}

@router.post("/projects/{project_id}/standup")
def get_standup(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return tech_lead_svc.generate_standup(project_id)

@router.post("/projects/{project_id}/lead/chat")
def chat_with_lead(project_id: str, req: LeadChatRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return tech_lead_svc.chat_with_lead(project_id, req.message)

@router.get("/projects/{project_id}/git")
def get_project_git_status(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return git_svc.get_git_status(p.workspace_path)

@router.post("/projects/{project_id}/git/init")
def init_project_git(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    res = git_svc.init_repository(p.workspace_path)
    return res

@router.get("/skills")
def list_global_skills():
    skills = skill_manager.list_available_skills()
    return [
        {
            "name": s.name,
            "title": s.title,
            "description": s.description,
            "allowed_tools": s.allowed_tools,
            "triggers": s.triggers,
            "tier": s.tier
        }
        for s in skills
    ]

@router.get("/projects/{project_id}/skills")
def get_project_skills(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    agents = store.list_agents(project_id)
    result = []
    for a in agents:
        skill = skill_manager.get_skill(a.skill_name or a.role, project_path=p.workspace_path)
        result.append({
            "role": a.role,
            "agent_status": a.status.value,
            "skill_name": skill.name,
            "skill_title": skill.title,
            "skill_tier": getattr(a, "skill_tier", None) or skill.tier,
            "description": skill.description,
            "allowed_tools": skill.allowed_tools
        })
    return result

@router.get("/projects/{project_id}/skills/{role}")
def get_agent_skill(project_id: str, role: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    skill = skill_manager.get_skill(role, project_path=p.workspace_path)
    return {
        "name": skill.name,
        "title": skill.title,
        "description": skill.description,
        "allowed_tools": skill.allowed_tools,
        "triggers": skill.triggers,
        "tier": skill.tier,
        "instructions": skill.instructions,
        "raw_content": skill.raw_content,
        "file_path": skill.file_path
    }

@router.put("/projects/{project_id}/skills/{role}")
def update_agent_skill(project_id: str, role: str, req: SkillUpdateRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    saved_path = skill_manager.save_custom_skill(
        project_path=p.workspace_path,
        role=role,
        content=req.content
    )
    skill = skill_manager.get_skill(role, project_path=p.workspace_path)
    store.set_agent_status(
        project_id=project_id,
        role=role,
        status="IDLE",
        skill_name=skill.name,
        skill_tier="project",
        skill_title=skill.title
    )
    return {"status": "SUCCESS", "file_path": saved_path, "tier": "project"}

@router.post("/skills/download")
def download_skill(req: DownloadSkillRequest):
    project_path = None
    if req.target == "project":
        if not req.project_id:
            raise HTTPException(status_code=400, detail="project_id is required when target is 'project'")
        p = store.get_project(req.project_id)
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        project_path = p.workspace_path

    try:
        skill = skill_manager.download_online_skill(
            url=req.url,
            skill_name=req.skill_name,
            target=req.target,
            project_path=project_path
        )
        return {
            "status": "SUCCESS",
            "message": f"Skill '{skill.name}' downloaded successfully.",
            "skill": {
                "name": skill.name,
                "title": skill.title,
                "description": skill.description,
                "tier": skill.tier,
                "file_path": skill.file_path,
                "allowed_tools": skill.allowed_tools
            }
        }
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to download skill: {err}")

@router.post("/projects/{project_id}/agents/{role}/assign-skill")
def assign_skill_to_agent(project_id: str, role: str, req: AssignSkillRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    agent = store.get_agent_status(project_id, role)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{role}' not found in project '{project_id}'")

    skill = skill_manager.get_skill(req.skill_name, project_path=p.workspace_path)
    updated_state = store.assign_agent_skill(
        project_id=project_id,
        role=role,
        skill_name=skill.name,
        skill_tier=skill.tier,
        skill_title=skill.title
    )
    return {
        "status": "SUCCESS",
        "project_id": project_id,
        "role": role,
        "skill_name": updated_state.skill_name,
        "skill_tier": updated_state.skill_tier,
        "skill_title": updated_state.skill_title
    }




