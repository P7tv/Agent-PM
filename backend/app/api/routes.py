from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
import asyncio
import subprocess
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator
from app.services.tech_lead_service import TechLeadService
from app.services.git_service import GitService
from app.services.skill_manager import SkillManager
from app.services.console_service import ConsoleService, parse_target_role
from app.api.websocket_hub import hub
from app.models.schemas import DownloadSkillRequest, AssignSkillRequest, SkillAddRequest, SkillRemoveRequest, SetSkillModeRequest, SprintRecord

router = APIRouter(prefix="/api")

# Default database in project directory
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "state.db")
store = StateStore(db_path=db_path)
pm = ProjectManager(store=store)
runner = AgentRunner(use_mock=False, store=store)
orchestrator = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
tech_lead_svc = TechLeadService(store=store, pm=pm)
git_svc = GitService()
skill_manager = SkillManager()
console_svc = ConsoleService()

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

class ConsoleChatRequest(BaseModel):
    message: str
    attachments: Optional[List[dict]] = None

class ApplyChangeRequest(BaseModel):
    filepath: str
    content: str
    commit_message: Optional[str] = None

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

@router.get("/projects/{project_id}/sprints", response_model=List[SprintRecord])
def get_project_sprints(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_sprints(project_id)

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
        meta = store.get_project_metadata(project_id)
        try:
            res = await runner.dispatch_agent_task(
                project_id=project_id,
                role=req.role,
                prompt=f"PM Directive: {req.message}",
                workspace_path=p.workspace_path,
                project_context=meta,
                event_callback=hub.broadcast
            )
            final_thought = res.get("response") or f"Acknowledged: {req.message}"
            store.set_agent_status(project_id, req.role, "IDLE", final_thought)
            await hub.broadcast("AGENT_STATE_UPDATE", {
                "project_id": project_id,
                "role": req.role,
                "status": "IDLE",
                "thought": final_thought
            })
        except Exception as e:
            store.set_agent_status(project_id, req.role, "IDLE", f"Note: {str(e)}")
            await hub.broadcast("AGENT_STATE_UPDATE", {
                "project_id": project_id,
                "role": req.role,
                "status": "IDLE",
                "thought": f"Note: {str(e)}"
            })
        
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
        base_role_skill = skill_manager.get_base_role_skill(a.role)
        result.append({
            "role": a.role,
            "agent_status": a.status.value,
            "skill_name": a.skill_name,
            "skill_title": a.skill_title,
            "skill_tier": getattr(a, "skill_tier", None) or "stock",
            "base_role_playbook": {
                "name": base_role_skill.name,
                "title": base_role_skill.title,
                "description": base_role_skill.description,
            } if base_role_skill else None,
            "skill_mode": getattr(a, "skill_mode", "AUTO"),
            "equipped_skills": getattr(a, "equipped_skills", [])
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

@router.post("/projects/{project_id}/agents/{role}/skills/add")
def add_agent_skill(project_id: str, role: str, req: SkillAddRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    agent = store.get_agent_status(project_id, role)
    equipped = agent.equipped_skills or []
    if req.skill_name not in equipped:
        equipped.append(req.skill_name)
    
    store.set_agent_status(
        project_id=project_id,
        role=role,
        status=agent.status.value,
        thought=agent.thought,
        current_task_id=agent.current_task_id,
        last_tool_call=agent.last_tool_call,
        skill_name=agent.skill_name,
        skill_tier=agent.skill_tier,
        skill_title=agent.skill_title,
        equipped_skills=equipped,
        skill_mode="MANUAL"
    )
    return {"status": "SUCCESS", "equipped_skills": equipped, "skill_mode": "MANUAL"}

@router.post("/projects/{project_id}/agents/{role}/skills/remove")
def remove_agent_skill(project_id: str, role: str, req: SkillRemoveRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    agent = store.get_agent_status(project_id, role)
    equipped = agent.equipped_skills or []
    if req.skill_name in equipped:
        equipped.remove(req.skill_name)
    
    mode = agent.skill_mode
    if not equipped:
        mode = "AUTO"
        
    store.set_agent_status(
        project_id=project_id,
        role=role,
        status=agent.status.value,
        thought=agent.thought,
        current_task_id=agent.current_task_id,
        last_tool_call=agent.last_tool_call,
        skill_name=agent.skill_name,
        skill_tier=agent.skill_tier,
        skill_title=agent.skill_title,
        equipped_skills=equipped,
        skill_mode=mode
    )
    return {"status": "SUCCESS", "equipped_skills": equipped, "skill_mode": mode}

@router.post("/projects/{project_id}/agents/{role}/skills/set-mode")
def set_agent_skill_mode(project_id: str, role: str, req: SetSkillModeRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if req.mode not in ["AUTO", "MANUAL"]:
        raise HTTPException(status_code=400, detail="Mode must be AUTO or MANUAL")
    
    agent = store.get_agent_status(project_id, role)
    store.set_agent_status(
        project_id=project_id,
        role=role,
        status=agent.status.value,
        thought=agent.thought,
        current_task_id=agent.current_task_id,
        last_tool_call=agent.last_tool_call,
        skill_name=agent.skill_name,
        skill_tier=agent.skill_tier,
        skill_title=agent.skill_title,
        equipped_skills=agent.equipped_skills,
        skill_mode=req.mode
    )
    return {"status": "SUCCESS", "skill_mode": req.mode}


# ──────────────────────────────────────────────────────────────
# Unified Team Console Endpoints
# ──────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/console/history")
def get_console_history(project_id: str, limit: int = 50):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return console_svc.get_history(project_id, limit=limit)

@router.post("/projects/{project_id}/console/upload")
async def upload_console_attachment(project_id: str, file: UploadFile = File(...)):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    upload_dir = os.path.join(p.workspace_path, ".agents", "attachments")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1]
    safe_name = f"{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(upload_dir, safe_name)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {"status": "SUCCESS", "filename": file.filename, "path": filepath, "url": f"/api/projects/{project_id}/attachments/{safe_name}"}

@router.get("/projects/{project_id}/attachments/{filename}")
def get_console_attachment(project_id: str, filename: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    filepath = os.path.join(p.workspace_path, ".agents", "attachments", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Attachment not found")

    return FileResponse(filepath)


@router.post("/projects/{project_id}/console/chat")
async def console_chat(project_id: str, req: ConsoleChatRequest, bg: BackgroundTasks):
    """Unified chat endpoint. Detects @Role mentions, routes to correct agent."""
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # Parse @Role mention
    target_role, clean_message = parse_target_role(req.message)

    # Record user message in console
    user_msg = console_svc.add_message(
        project_id=project_id,
        sender="user",
        content=req.message,
        msg_type="user_chat",
        attachments=req.attachments
    )

    # Broadcast back to UI so the user can see their own message immediately
    await hub.broadcast("CONSOLE_MESSAGE", user_msg.to_dict())

    # Get conversation context for the agent
    conversation_context = console_svc.get_recent_context(project_id, count=5)
    meta = store.get_project_metadata(project_id)

    async def run_console_chat():
        # If @Team, dispatch directive to orchestrator
        if target_role == "Team":
            console_svc.add_message(
                project_id=project_id,
                sender="system",
                content=f"📢 Broadcasting directive to full team: {clean_message}",
                msg_type="system"
            )
            await hub.broadcast("CONSOLE_MESSAGE", {
                "project_id": project_id,
                "sender": "system",
                "content": f"📢 Broadcasting directive to full team: {clean_message}",
                "msg_type": "system"
            })
            await orchestrator.execute_pm_directive(
                project_id=project_id,
                directive=clean_message,
                event_callback=hub.broadcast
            )
            return

        # Single agent chat
        store.set_agent_status(project_id, target_role, "THINKING", f"Responding to PM: {clean_message[:80]}")
        await hub.broadcast("AGENT_STATE_UPDATE", {
            "project_id": project_id,
            "role": target_role,
            "status": "THINKING"
        })

        try:
            result = await runner.dispatch_chat_task(
                project_id=project_id,
                role=target_role,
                message=clean_message,
                workspace_path=p.workspace_path,
                project_context=meta,
                conversation_context=conversation_context,
                attachments=req.attachments
            )

            response_text = result.get("response", "")
            code_proposals = result.get("code_proposals", [])

            msg_type = "code_proposal" if code_proposals else "agent_response"

            agent_msg = console_svc.add_message(
                project_id=project_id,
                sender=target_role,
                content=response_text,
                msg_type=msg_type,
                role=target_role,
                code_proposals=code_proposals
            )

            await hub.broadcast("CONSOLE_MESSAGE", agent_msg.to_dict())

            store.set_agent_status(project_id, target_role, "IDLE", response_text[:120])
            await hub.broadcast("AGENT_STATE_UPDATE", {
                "project_id": project_id,
                "role": target_role,
                "status": "IDLE",
                "thought": response_text[:120]
            })

        except Exception as e:
            error_msg = f"Error from {target_role}: {str(e)[:200]}"
            console_svc.add_message(
                project_id=project_id,
                sender="system",
                content=error_msg,
                msg_type="system"
            )
            await hub.broadcast("CONSOLE_MESSAGE", {
                "project_id": project_id,
                "sender": "system",
                "content": error_msg,
                "msg_type": "system"
            })
            store.set_agent_status(project_id, target_role, "IDLE", error_msg[:80])

    bg.add_task(run_console_chat)

    return {
        "status": "SENT",
        "target_role": target_role,
        "message_id": user_msg.message_id
    }


@router.post("/projects/{project_id}/apply-change")
def apply_code_change(project_id: str, req: ApplyChangeRequest):
    """Apply a code proposal: write file to workspace and create git commit."""
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # Resolve filepath relative to workspace
    if os.path.isabs(req.filepath):
        full_path = req.filepath
    else:
        full_path = os.path.join(p.workspace_path, req.filepath)

    # Security: ensure file is inside the workspace
    real_workspace = os.path.realpath(p.workspace_path)
    real_target = os.path.realpath(full_path)
    if not real_target.startswith(real_workspace):
        raise HTTPException(status_code=403, detail="File path must be inside the project workspace")

    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write the file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(req.content)

        # Git add + commit
        commit_msg = req.commit_message or f"Apply code change: {os.path.basename(req.filepath)}"
        try:
            subprocess.run(["git", "add", full_path], cwd=p.workspace_path, capture_output=True, timeout=10)
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=p.workspace_path, capture_output=True, timeout=10
            )
        except Exception:
            pass  # Git commit is best-effort

        console_svc.add_message(
            project_id=project_id,
            sender="system",
            content=f"✅ Applied code change to `{req.filepath}` and committed.",
            msg_type="system"
        )

        return {
            "status": "APPLIED",
            "filepath": req.filepath,
            "full_path": full_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")


@router.post("/projects/{project_id}/run-tests")
async def run_tests(project_id: str):
    """Execute test commands in the project workspace and return real output."""
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    workspace = p.workspace_path

    # Detect test framework
    test_cmd = None
    if os.path.exists(os.path.join(workspace, "package.json")):
        test_cmd = ["npm", "test", "--", "--watchAll=false"]
    elif os.path.exists(os.path.join(workspace, "pytest.ini")) or os.path.exists(os.path.join(workspace, "setup.py")):
        test_cmd = ["python", "-m", "pytest", "-v"]
    elif os.path.exists(os.path.join(workspace, "go.mod")):
        test_cmd = ["go", "test", "./..."]
    elif os.path.exists(os.path.join(workspace, "Cargo.toml")):
        test_cmd = ["cargo", "test"]
    else:
        # Default: try npm test
        test_cmd = ["npm", "test", "--", "--watchAll=false"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *test_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)

        output = stdout.decode("utf-8", errors="ignore")
        errors = stderr.decode("utf-8", errors="ignore")
        passed = proc.returncode == 0

        result = {
            "status": "PASSED" if passed else "FAILED",
            "exit_code": proc.returncode,
            "stdout": output[-3000:],  # Last 3KB
            "stderr": errors[-1000:],
            "command": " ".join(test_cmd)
        }

        console_svc.add_message(
            project_id=project_id,
            sender="QATester",
            content=f"Test run {'✅ PASSED' if passed else '❌ FAILED'}: `{' '.join(test_cmd)}`",
            msg_type="qa_result",
            qa_results=result
        )

        return result

    except asyncio.TimeoutError:
        return {
            "status": "TIMEOUT",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Test execution timed out after 120 seconds.",
            "command": " ".join(test_cmd)
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "command": " ".join(test_cmd)
        }
