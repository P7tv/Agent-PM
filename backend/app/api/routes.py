from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator
from app.api.websocket_hub import hub

router = APIRouter(prefix="/api")

# Default database in project directory
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "state.db")
store = StateStore(db_path=db_path)
pm = ProjectManager(store=store)
runner = AgentRunner(use_mock=False)
orchestrator = Orchestrator(store=store, project_manager=pm, agent_runner=runner)

class CreateProjectRequest(BaseModel):
    project_id: str
    name: str
    workspace_path: str
    auto_pilot: bool = False

class DirectiveRequest(BaseModel):
    directive: str

class ApprovalDecisionRequest(BaseModel):
    decision: str  # APPROVED / REJECTED

class WhisperRequest(BaseModel):
    role: str
    message: str

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
