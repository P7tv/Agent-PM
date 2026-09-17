from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
import os
import sys
import time
import shutil
import uuid
import asyncio
import subprocess
import signal
import shlex
from pathlib import Path
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator
from app.services.tech_lead_service import TechLeadService
from app.services.git_service import GitService
from app.services.skill_manager import SkillManager
from app.services.console_service import ConsoleService, parse_target_role, is_actionable_directive
from app.services.verification import load_project_config, detect_verification_commands
from app.services.sprint_queue import SprintQueue
from app.services.workspace_session import WorkspaceSession
from app.api.websocket_hub import hub
from app.services.event_journal import EventJournal
from app.models.schemas import (
    DownloadSkillRequest, AssignSkillRequest, SkillAddRequest, SkillRemoveRequest,
    SetSkillModeRequest, SprintRecord, QueueItem, CustomAgentCreateRequest, AutoGenerateRosterRequest,
    TaskItem, BacklogItem, ProjectMemory, AgentActivityLog
)

router = APIRouter(prefix="/api")

# Default database in project directory
db_path = os.environ.get("PM_STATE_DB") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "state.db")
store = StateStore(db_path=db_path)
hub.journal = EventJournal(db_path)
pm = ProjectManager(store=store)
runner = AgentRunner(use_mock=False, store=store)
orchestrator = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
sprint_queue = SprintQueue(store=store, orchestrator=orchestrator, broadcast_fn=hub.broadcast)
tech_lead_svc = TechLeadService(store=store, pm=pm)
git_svc = GitService()
skill_manager = SkillManager()
console_svc = ConsoleService(store=store)
preview_processes = {}
preview_sources = {}
preview_sessions = {}
preview_locks = {}


def _preview_spec(project, workspace_override=None):
    config = load_project_config(project.workspace_path)
    preview = config.get("preview", {}) if isinstance(config.get("preview"), dict) else {}
    command = preview.get("command")
    if isinstance(command, str):
        args = shlex.split(command)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        args = command
    else:
        args = []
    root = Path(workspace_override or project.workspace_path).resolve()
    cwd = (root / str(preview.get("cwd", "."))).resolve()
    try:
        cwd.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Preview cwd must stay inside the project workspace")
    if not args or not cwd.is_dir():
        raise HTTPException(status_code=409, detail="Preview command is not configured correctly")
    return args, str(cwd), preview.get("url")


async def _stop_preview(project_id: str):
    async with preview_locks.setdefault(project_id, asyncio.Lock()):
        await _stop_preview_unlocked(project_id)


async def _stop_preview_unlocked(project_id: str):
    process = preview_processes.pop(project_id, None)
    if process and process.poll() is None:
        if os.name != 'nt':
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        else:
            process.terminate()
        try:
            await asyncio.to_thread(process.wait, 5)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            else:
                process.kill()
            await asyncio.to_thread(process.wait, 5)
    session = preview_sessions.pop(project_id, None)
    if session:
        session.close(delete=False)
    preview_sources.pop(project_id, None)

class SkillUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=512 * 1024)

class AgentIdentityRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    persona: str = Field(min_length=1, max_length=4000)

class PromptPreviewRequest(BaseModel):
    message: str = Field(default="", max_length=16000)
    mode: Optional[Literal["consultation", "planning", "design", "implementation", "verification-analysis", "review"]] = None

def registered_agent(project_id, role):
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    agent = next((item for item in store.list_agents(project_id) if item.role == role), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

def required_skill(name, workspace):
    try:
        return skill_manager.get_skill(name, workspace, required=True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.put("/projects/{project_id}/agents/{role}/identity")
async def update_agent_identity(project_id: str, role: str, req: AgentIdentityRequest):
    agent = registered_agent(project_id, role)
    if not req.display_name.strip() or not req.persona.strip():
        raise HTTPException(status_code=400, detail="Name and persona must not be blank")
    store.set_agent_status(project_id, role, agent.status.value, thought=agent.thought,
        display_name=req.display_name.strip(), persona=req.persona.strip(), persona_source="explicit")
    updated = store.get_agent_status(project_id, role)
    await hub.broadcast("AGENT_STATE_UPDATE", updated.model_dump(mode="json"))
    return updated

@router.post("/projects/{project_id}/agents/{role}/prompt-preview")
def preview_agent_prompt(project_id: str, role: str, req: PromptPreviewRequest):
    registered_agent(project_id, role)
    project = store.get_project(project_id)
    try:
        bundle = runner.prepare_prompt(project_id, role, project.workspace_path, req.message,
            store.get_project_metadata(project_id), mode=req.mode)
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"system_prompt": bundle.system, "trace": bundle.trace}

@router.get("/projects/{project_id}/agents/{role}/prompt-traces")
def get_agent_prompt_traces(project_id: str, role: str):
    registered_agent(project_id, role)
    return store.list_prompt_traces(project_id, role)

class CreateProjectRequest(BaseModel):
    project_id: str
    name: str
    workspace_path: str
    auto_pilot: bool = False

class LeadChatRequest(BaseModel):
    message: str

class DirectiveRequest(BaseModel):
    directive: str
    acceptance_criteria: List[str] = Field(default_factory=list, max_length=50)
    protected_paths: List[str] = Field(default_factory=list, max_length=50)

    @field_validator("directive")
    @classmethod
    def nonempty_directive(cls, value):
        if not value.strip():
            raise ValueError("Directive cannot be empty")
        return value.strip()


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"]
    feedback: str = ""

class RetrySprintRequest(BaseModel):
    stage: Literal["PLANNING", "IMPLEMENTATION", "QA", "REVIEWER", "FINAL"] = "QA"

class WhisperRequest(BaseModel):
    role: str
    message: str = Field(min_length=1, max_length=4000)

class ValidatePathRequest(BaseModel):
    path: str

class ConsoleChatRequest(BaseModel):
    message: str
    attachments: Optional[List[dict]] = None
    is_directive: Optional[bool] = False

class ApplyChangeRequest(BaseModel):
    filepath: str
    content: str
    commit_message: Optional[str] = None

class CreateBacklogItemRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    category: Optional[str] = "feature"
    priority: Optional[str] = "NORMAL"

class UpdateBacklogItemRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None

class CreateMemoryRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = "architecture"

class QueuePriorityRequest(BaseModel):
    priority: Literal["URGENT", "HIGH", "NORMAL", "LOW"]

class QueueReorderRequest(BaseModel):
    direction: Literal["up", "down"]

class GitRemoteRequest(BaseModel):
    name: str = "origin"
    url: str

class GitPushPullRequest(BaseModel):
    remote: str = "origin"
    branch: Optional[str] = None

class GitBranchRequest(BaseModel):
    branch_name: str
    checkout: Optional[bool] = True

class GitCheckoutRequest(BaseModel):
    branch_name: str

@router.post("/projects/validate-path")
def validate_path(req: ValidatePathRequest):
    valid, msg, meta = pm.inspector.validate_guardrails(req.path)
    return {
        "valid": valid,
        "message": msg,
        "metadata": meta
    }

@router.get("/runtime/probe")
async def probe_runtime():
    from app.services.agent_runner import AGY_PATH
    from app.services.runtime_adapter import AntigravityAdapter
    if runner.selected_backend() != 'cli':
        return {**runner.runtime_status(), 'probe_status': 'NOT_RUN'}
    try:
        return await AntigravityAdapter(AGY_PATH).get_capabilities(str(Path(db_path).parent))
    except (OSError, TimeoutError) as error:
        return {'probe_status': 'FAILED', 'error': str(error)}


@router.get("/runtime")
def get_runtime():
    return runner.runtime_status()


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
    await sprint_queue.stop_project(project_id)
    await _stop_preview(project_id)
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

@router.get("/projects/{project_id}/sprints/{sprint_id}/tasks", response_model=List[TaskItem])
def get_sprint_tasks(project_id: str, sprint_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    return store.get_sprint_tasks(sprint_id)

@router.get("/projects/{project_id}/sprints/{sprint_id}/report")
def get_sprint_report(project_id: str, sprint_id: str):
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    logs = store.get_agent_sprint_logs(sprint_id) if hasattr(store, "get_agent_sprint_logs") else []
    return {"sprint": sprint, "tasks": store.get_sprint_tasks(sprint_id), "agent_logs": logs}

@router.post("/projects/{project_id}/sprints/{sprint_id}/retry", response_model=QueueItem)
async def retry_sprint(project_id: str, sprint_id: str, req: RetrySprintRequest):
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    if sprint.status not in {"FAILED", "REJECTED", "PAUSED", "INTERRUPTED"}:
        raise HTTPException(status_code=409, detail="Only failed or rejected sprints can be retried")
    if not sprint.checkpoint_path or not os.path.isdir(sprint.checkpoint_path):
        raise HTTPException(status_code=409, detail="This sprint has no preserved checkpoint")
    plan = sprint.execution_plan or {}
    if plan.get('ownership_violation'):
        raise HTTPException(status_code=409, detail='Checkpoint contains edits outside task ownership; inspect its files and start a new run.')
    if plan.get("checkpoint_stage") not in {"PLANNING", "IMPLEMENTATION", "QA", "REVIEWER", "FINAL"}:
        raise HTTPException(status_code=409, detail="Implementation did not finish. Re-run the directive instead of resuming QA.")
    if sprint.change_evidence.get("applied_to_project") is True:
        raise HTTPException(status_code=409, detail="Checkpoint changes have already been applied to the project.")
    if project_id in orchestrator._active_projects:
        raise HTTPException(status_code=409, detail='Agent process is still stopping. Wait for pause to finish before Resume.')
    if any(item.status == "RUNNING" for item in store.get_sprints(project_id)):
        raise HTTPException(status_code=409, detail="This project already has an active sprint. Wait for it to finish before resuming.")
    for pending in store.get_all_queue_items():
        if pending.project_id == project_id and pending.source_sprint_id == sprint_id:
            return pending
    manifest_hash = plan.get("checkpoint_manifest_hash")
    if not manifest_hash:
        raise HTTPException(status_code=409, detail="Legacy checkpoint has no initial baseline. Inspect or recover its files instead of automatic Resume.")
    try:
        manifest = WorkspaceSession.load_checkpoint_manifest(sprint.checkpoint_path, manifest_hash)
        project = store.get_project(project_id)
        if not project or manifest["original"] != str(Path(project.workspace_path).resolve()):
            raise ValueError("Checkpoint belongs to another workspace")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    if preview_sources.get(project_id, {}).get('scope') == 'CHECKPOINT':
        await _stop_preview(project_id)
    item = sprint_queue.enqueue(
        project_id, sprint.directive, priority="URGENT",
        acceptance_criteria=plan.get("acceptance_criteria", []),
        protected_paths=plan.get("protected_paths", []),
        source_sprint_id=sprint_id, resume_from=req.stage,
    )
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "queue_id": item.queue_id})
    return item

@router.get("/projects/{project_id}/config")
def get_project_config(project_id: str):
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    config = load_project_config(project.workspace_path)
    checks = detect_verification_commands(project.workspace_path)
    preview = config.get("preview", {}) if isinstance(config.get("preview", {}), dict) else {}
    return {
        "config_file": next((name for name in (".agent-pm.yml", ".agent-pm.yaml") if os.path.isfile(os.path.join(project.workspace_path, name))), None),
        "verification_checks": [{"name": c["name"], "kind": c["kind"], "required": c.get("required", True)} for c in checks],
        "protected_paths": config.get("protected_paths", []),
        "preview": {"url": preview.get("url"), "command": preview.get("command")},
    }

@router.get("/projects/{project_id}/preview")
def get_preview_status(project_id: str):
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    process = preview_processes.get(project_id)
    config = load_project_config(project.workspace_path)
    preview = config.get("preview", {}) if isinstance(config.get("preview"), dict) else {}
    return {"running": bool(process and process.poll() is None), "url": preview.get("url"),
            **preview_sources.get(project_id, {"scope": "PROJECT"})}

@router.post("/projects/{project_id}/preview")
async def start_preview(project_id: str, sprint_id: Optional[str] = None):
    async with preview_locks.setdefault(project_id, asyncio.Lock()):
        return await _start_preview_locked(project_id, sprint_id)


async def _start_preview_locked(project_id: str, sprint_id: Optional[str] = None):
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    existing = preview_processes.get(project_id)
    source = preview_sources.get(project_id, {})
    if existing and existing.poll() is None:
        if source.get('sprint_id') == sprint_id:
            return {"running": True, "url": load_project_config(project.workspace_path).get("preview", {}).get("url"), **source}
        await _stop_preview_unlocked(project_id)
    execution_workspace = project.workspace_path
    if sprint_id:
        sprint = store.get_sprint(sprint_id)
        if not sprint or sprint.project_id != project_id:
            raise HTTPException(status_code=404, detail='Sprint not found for this project')
        active_queue = any(item.project_id == project_id for item in store.get_all_queue_items())
        if sprint.status not in {'PAUSED', 'INTERRUPTED', 'FAILED', 'REJECTED'} or project_id in orchestrator._active_projects or active_queue:
            raise HTTPException(status_code=409, detail='Checkpoint preview requires a stopped sprint')
        try:
            Path(sprint.checkpoint_path or '').resolve().relative_to(Path(db_path).resolve().parent / '.agentpm-runs')
            manifest_hash = sprint.execution_plan.get('checkpoint_manifest_hash')
            if not manifest_hash: raise ValueError('Checkpoint has no trusted baseline')
            session = WorkspaceSession(project.workspace_path, reuse_path=sprint.checkpoint_path,
                                       expected_manifest_hash=manifest_hash)
            execution_workspace = str(session.workspace)
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=409, detail=str(error))
        args, cwd, url = _preview_spec(project, execution_workspace)
        preview_sessions[project_id] = session
        try:
            await asyncio.to_thread(session.mount_dependencies)
        except Exception:
            await _stop_preview_unlocked(project_id)
            raise
    args, cwd, url = _preview_spec(project, execution_workspace)
    try:
        process = await asyncio.to_thread(
            subprocess.Popen, args, cwd=cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except OSError as exc:
        await _stop_preview_unlocked(project_id)
        raise HTTPException(status_code=500, detail=f"Could not start preview: {exc}")
    preview_processes[project_id] = process
    preview_sources[project_id] = {'scope': 'CHECKPOINT' if sprint_id else 'PROJECT',
                                   'sprint_id': sprint_id, 'workspace': execution_workspace}
    await asyncio.sleep(0.25)
    if process.poll() is not None:
        await _stop_preview_unlocked(project_id)
        raise HTTPException(status_code=500, detail="Preview process exited during startup")
    return {"running": True, "url": url, **preview_sources.get(project_id, {})}

@router.delete("/projects/{project_id}/preview")
async def stop_preview(project_id: str):
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    await _stop_preview(project_id)
    return {"running": False}

@router.get("/projects/{project_id}/sprints/{sprint_id}/agent-logs")
def get_sprint_agent_logs(project_id: str, sprint_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    if hasattr(store, "get_agent_sprint_logs"):
        return store.get_agent_sprint_logs(sprint_id)
    return []

@router.get("/projects/{project_id}/sprints/{sprint_id}/export")
def export_sprint_release_notes(project_id: str, sprint_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    
    started_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(sprint.started_at)) if sprint.started_at else "N/A"
    completed_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(sprint.completed_at)) if sprint.completed_at else "In Progress"
    duration = f"{int(sprint.completed_at - sprint.started_at)}s" if sprint.completed_at and sprint.started_at else "N/A"
    criteria_md = "\n".join(f"- {item}" for item in sprint.execution_plan.get("acceptance_criteria", [])) or "- Not recorded"
    check_lines = [
        f"- **{check.get('status', 'UNKNOWN')}** — {check.get('name', 'check')}"
        for check in sprint.verification_report.get("checks", [])
    ]
    checks_md = "\n".join(check_lines) or f"- {sprint.verification_report.get('status', 'Not recorded')}"
    changed_lines = []
    for kind in ("added", "modified", "deleted"):
        changed_lines.extend(f"- `{path}` ({kind})" for path in sprint.change_evidence.get(kind, []))
    changes_md = "\n".join(changed_lines) or "- No file evidence recorded"
    findings_md = "\n".join(f"- {item}" for item in sprint.review_verdict.get("findings", [])) or "- None"
    
    md = f"""# 🚀 Sprint Release Notes: {sprint.sprint_id}
**Project:** {p.name} (`{project_id}`)  
**Directive / Objective:** {sprint.directive}  
**Status:** `{sprint.status}`  

---

## ⏱ Execution Summary
- **Started At:** {started_str}
- **Completed At:** {completed_str}
- **Total Duration:** {duration}
- **Tasks Executed:** {sprint.tasks_count}
- **LLM Engine / Backend:** `{sprint.backend_used}`
- **Total Tokens Consumed:** {sprint.total_tokens:,} tokens

---

## 📝 Release Summary & Highlights
{sprint.release_summary or "No release summary recorded for this sprint."}

## ✅ Acceptance Criteria
{criteria_md}

## 🧪 Verification
{checks_md}

## 📁 Change Evidence
{changes_md}

## 🔍 Review Verdict
**{sprint.review_verdict.get("verdict", "Not recorded")}**
{findings_md}

---
*Generated automatically by Agent-PM Autonomous Development Dashboard.*
"""
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="sprint-{sprint_id}-release-notes.md"'}
    )

@router.get("/projects/{project_id}/queue", response_model=List[QueueItem])
def get_project_queue(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return sprint_queue.list_queue(project_id)

@router.post("/projects/{project_id}/queue", response_model=QueueItem)
async def enqueue_project_directive(project_id: str, req: DirectiveRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if not runner.runtime_status()["available"]:
        raise HTTPException(status_code=503, detail=runner.runtime_status()["message"])
    item = sprint_queue.enqueue(
        project_id, req.directive,
        acceptance_criteria=req.acceptance_criteria, protected_paths=req.protected_paths,
    )
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "queue_id": item.queue_id})
    return item

@router.delete("/projects/{project_id}/queue/{queue_id}")
async def cancel_queue_directive(project_id: str, queue_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    item = store.get_queue_item(queue_id)
    if not item or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Queue item not found for this project")
    cancelled = sprint_queue.cancel_item(queue_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Queue item not found or already running")
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "cancelled_id": queue_id})
    return {"status": "CANCELLED", "queue_id": queue_id}

@router.get("/queue/all")
def get_all_queue():
    items = store.get_all_queue_items()
    projects = {p.project_id: p.name for p in store.list_projects()}
    result = []
    for it in items:
        result.append({
            "queue_id": it.queue_id,
            "project_id": it.project_id,
            "project_name": projects.get(it.project_id, it.project_id),
            "directive": it.directive,
            "status": it.status,
            "position": it.position,
            "priority": getattr(it, "priority", "NORMAL"),
            "created_at": it.created_at
        })
    return result
@router.delete("/queue/{queue_id}")
async def cancel_global_queue_item(queue_id: str):
    cancelled = sprint_queue.cancel_item(queue_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Queue item not found or already running")
    await hub.broadcast("QUEUE_UPDATED", {"cancelled_id": queue_id})
    return {"status": "CANCELLED", "queue_id": queue_id}

@router.patch("/queue/{queue_id}/priority")
async def set_global_queue_priority(queue_id: str, req: QueuePriorityRequest):
    updated = store.set_queue_priority(queue_id, req.priority)
    if not updated:
        raise HTTPException(status_code=404, detail="Queue item not found")
    await hub.broadcast("QUEUE_UPDATED", {"queue_id": queue_id, "priority": req.priority})
    return {"status": "SUCCESS", "queue_id": queue_id, "priority": req.priority}

@router.post("/queue/{queue_id}/reorder")
async def reorder_global_queue_item(queue_id: str, req: QueueReorderRequest):
    reordered = store.reorder_queue_item(queue_id, req.direction)
    if not reordered:
        raise HTTPException(status_code=400, detail="Cannot move item in that direction")
    await hub.broadcast("QUEUE_UPDATED", {"queue_id": queue_id, "direction": req.direction})
    return {"status": "SUCCESS", "queue_id": queue_id, "direction": req.direction}

@router.patch("/projects/{project_id}/queue/{queue_id}/priority")
async def set_queue_item_priority(project_id: str, queue_id: str, req: QueuePriorityRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    item = store.get_queue_item(queue_id)
    if not item or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Queue item not found for this project")
    updated = store.set_queue_priority(queue_id, req.priority)
    if not updated:
        raise HTTPException(status_code=404, detail="Queue item not found")
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "queue_id": queue_id, "priority": req.priority})
    return {"status": "SUCCESS", "queue_id": queue_id, "priority": req.priority}

@router.post("/projects/{project_id}/queue/{queue_id}/reorder")
async def reorder_queue_item(project_id: str, queue_id: str, req: QueueReorderRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    item = store.get_queue_item(queue_id)
    if not item or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Queue item not found for this project")
    reordered = store.reorder_queue_item(queue_id, req.direction)
    if not reordered:
        raise HTTPException(status_code=400, detail="Cannot move item in that direction")
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id})
    return {"status": "SUCCESS", "queue_id": queue_id, "direction": req.direction}

# ── Backlog Endpoints ─────────────────────────────────────────
@router.get("/projects/{project_id}/backlog", response_model=List[BacklogItem])
def get_project_backlog(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_backlog_items(project_id)

@router.post("/projects/{project_id}/backlog", response_model=BacklogItem)
async def create_backlog_item(project_id: str, req: CreateBacklogItemRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    item = store.create_backlog_item(
        project_id=project_id,
        title=req.title,
        description=req.description or "",
        category=req.category or "feature",
        priority=req.priority or "NORMAL"
    )
    await hub.broadcast("BACKLOG_UPDATED", {"project_id": project_id, "item_id": item.item_id})
    return item

@router.put("/projects/{project_id}/backlog/{item_id}", response_model=BacklogItem)
async def update_backlog_item(project_id: str, item_id: str, req: UpdateBacklogItemRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    updated = store.update_backlog_item(
        item_id=item_id,
        title=req.title,
        description=req.description,
        category=req.category,
        priority=req.priority,
        status=req.status
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    await hub.broadcast("BACKLOG_UPDATED", {"project_id": project_id, "item_id": item_id})
    return updated

@router.delete("/projects/{project_id}/backlog/{item_id}")
async def delete_backlog_item(project_id: str, item_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    deleted = store.delete_backlog_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    await hub.broadcast("BACKLOG_UPDATED", {"project_id": project_id, "deleted_id": item_id})
    return {"status": "DELETED", "item_id": item_id}

@router.post("/projects/{project_id}/backlog/{item_id}/promote")
async def promote_backlog_item_to_sprint(project_id: str, item_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    items = store.get_backlog_items(project_id)
    target = next((it for it in items if it.item_id == item_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    
    directive_text = f"{target.title}"
    if target.description:
        directive_text += f" - {target.description}"
    queue_item = sprint_queue.enqueue(project_id, directive_text, priority=target.priority)
    store.update_backlog_item(item_id, status="QUEUED")

    await hub.broadcast("BACKLOG_UPDATED", {"project_id": project_id, "item_id": item_id, "status": "QUEUED"})
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "queue_id": queue_item.queue_id})
    return {"status": "PROMOTED", "queue_id": queue_item.queue_id, "item_id": item_id}

# ── Project Memories Endpoints ─────────────────────────────────
@router.get("/projects/{project_id}/memories", response_model=List[ProjectMemory])
def get_project_memories(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_project_memories(project_id)

@router.post("/projects/{project_id}/memories", response_model=ProjectMemory)
async def add_project_memory(project_id: str, req: CreateMemoryRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    mem = store.add_project_memory(
        project_id=project_id,
        title=req.title,
        content=req.content,
        category=req.category or "architecture"
    )
    await hub.broadcast("PROJECT_MEMORY_UPDATED", {"project_id": project_id, "memory_id": mem.memory_id})
    return mem

@router.delete("/projects/{project_id}/memories/{memory_id}")
async def delete_project_memory(project_id: str, memory_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    deleted = store.delete_project_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory item not found")
    await hub.broadcast("PROJECT_MEMORY_UPDATED", {"project_id": project_id, "deleted_id": memory_id})
    return {"status": "DELETED", "memory_id": memory_id}

# ── Agent Performance Analytics & Metrics Endpoints ───────────
@router.get("/projects/{project_id}/agents/metrics")
def get_project_agent_metrics(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_agent_metrics(project_id)

@router.get("/projects/{project_id}/agents/{role}/metrics")
def get_role_metrics(project_id: str, role: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    all_metrics = store.get_agent_metrics(project_id)
    return all_metrics.get(role, {
        "total_actions": 0,
        "total_tokens": 0,
        "avg_duration_seconds": 0.0,
        "success_rate": 100.0
    })

@router.get("/projects/{project_id}/agents/activities", response_model=List[AgentActivityLog])
def get_agent_activities(project_id: str, role: Optional[str] = None, limit: int = 50):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.list_agent_activities(project_id, role=role, limit=limit)

@router.get("/projects/{project_id}/files")
def get_project_files(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    ws_path = p.workspace_path
    if not ws_path or not os.path.exists(ws_path):
        return {"files": []}
    
    files = []
    IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv", ".idea", ".vscode", "dist", "build"}
    
    real_ws = os.path.realpath(ws_path)
    try:
        for root, dirs, filenames in os.walk(real_ws):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
            for d in dirs:
                full_d = os.path.join(root, d)
                rel_d = os.path.relpath(full_d, real_ws).replace("\\", "/")
                files.append({"name": d, "path": rel_d, "is_dir": True})
            for f in filenames:
                if f.startswith('.'):
                    continue
                full_f = os.path.join(root, f)
                rel_f = os.path.relpath(full_f, real_ws).replace("\\", "/")
                files.append({"name": f, "path": rel_f, "is_dir": False})
            if len(files) > 500:
                break
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    files.sort(key=lambda x: (not x["is_dir"], x["path"].lower()))
    return {"files": files}

@router.get("/projects/{project_id}/files/content")
def get_project_file_content(project_id: str, path: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    ws_path = p.workspace_path
    if not ws_path or not os.path.exists(ws_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    
    real_ws = os.path.realpath(ws_path)
    target_path = os.path.realpath(os.path.join(real_ws, path))
    
    # Path traversal protection
    if os.path.commonpath([real_ws, target_path]) != real_ws or not os.path.isfile(target_path):
        raise HTTPException(status_code=400, detail="Invalid file path or access denied")
    
    try:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(100000)
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/agents")
async def add_project_agent(project_id: str, req: CustomAgentCreateRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    clean_role = "".join(c for c in req.role if c.isalnum() or c in ("_", "-"))
    if not clean_role:
        raise HTTPException(status_code=400, detail="Invalid role identifier")
        
    agent = store.add_agent(
        project_id=project_id,
        role=clean_role,
        title=req.title,
        description=req.description,
        skill_name=req.skill_name,
        skill_tier=req.skill_tier or "stock"
    )
    await hub.broadcast("AGENT_STATE_UPDATE", {
        "project_id": project_id,
        "role": clean_role,
        "status": "IDLE",
        "thought": req.description
    })
    return agent

@router.delete("/projects/{project_id}/agents/{role}")
async def delete_project_agent(project_id: str, role: str):
    if role == "TechLead":
        raise HTTPException(status_code=400, detail="Cannot delete project TechLead")
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    deleted = store.delete_agent(project_id, role)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found in project")
        
    await hub.broadcast("AGENT_DELETED", {
        "project_id": project_id,
        "role": role
    })
    return {"status": "DELETED", "role": role}

@router.post("/projects/{project_id}/agents/auto-generate")
async def auto_generate_project_agents(project_id: str, req: AutoGenerateRosterRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    res = tech_lead_svc.auto_generate_roster(project_id, replace_existing=req.replace_existing)
    await hub.broadcast("AGENT_ROSTER_UPDATED", {
        "project_id": project_id,
        "agents": res.get("agents", [])
    })
    return res

@router.get("/projects/{project_id}/approvals")
def get_project_approvals(project_id: str):
    return store.get_pending_approvals(project_id)

@router.post("/projects/{project_id}/approvals/{request_id}")
async def resolve_approval(project_id: str, request_id: str, req: ApprovalDecisionRequest):
    if not any(a.request_id == request_id for a in store.get_pending_approvals(project_id)):
        raise HTTPException(status_code=404, detail="Pending approval not found for this project")
    approval = next(item for item in store.get_pending_approvals(project_id) if item.request_id == request_id)
    if approval.gate_type == 'PLAN_APPROVAL' and req.decision == 'APPROVED':
        active = next((item for item in store.get_sprints(project_id) if item.status == 'RUNNING'), None)
        questions = (active.execution_plan.get('product_brief', {}).get('questions', []) if active else [])
        if any(item.get('blocking') and item.get('status') == 'OPEN' for item in questions) and not req.feedback.strip():
            raise HTTPException(status_code=409, detail='กรุณาตอบคำถามที่ต้องทราบก่อนเริ่มในช่อง feedback แล้วจึงอนุมัติ')
    store.resolve_approval(request_id, req.decision)
    # Signal the orchestrator to unblock the pipeline
    orchestrator.resolve_gate(request_id, req.decision, req.feedback)
    await hub.broadcast("DECISION_GATE_RESOLVED", {
        "project_id": project_id,
        "request_id": request_id,
        "decision": req.decision,
        "feedback": req.feedback,
    })
    return {"status": "RESOLVED", "decision": req.decision}

@router.post("/projects/{project_id}/whisper")
async def whisper_to_agent(project_id: str, req: WhisperRequest, bg: BackgroundTasks):
    registered_agent(project_id, req.role)
    active = next((item for item in store.get_sprints(project_id) if item.status == "RUNNING"), None)
    if not active:
        raise HTTPException(status_code=409, detail="ยังไม่มี Sprint ที่กำลังทำงาน ใช้โหมดปรึกษาหรือสั่งงานทีมเพื่อเริ่มงาน")
    if active.execution_plan.get("checkpoint_stage") == "FINAL":
        raise HTTPException(status_code=409, detail="กำลังนำไฟล์เข้าโปรเจกต์ ส่งข้อกำหนดนี้ในรอบถัดไป")
    scheduled_roles = {'TechLead', 'Architect'} | set(active.execution_plan.get('roles', [])) | set(active.execution_plan.get('quality_roles', []))
    if req.role not in scheduled_roles:
        raise HTTPException(status_code=409, detail="Agent นี้ยังไม่มีขั้นตอนในแผนของรอบงาน รอแผนหรือส่งข้อกำหนดให้ TechLead")
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="Instruction must not be blank")
    if sum(len(item['message']) for item in store.get_sprint_instructions(active.sprint_id)) + len(req.message) > 8000:
        raise HTTPException(status_code=409, detail="ข้อกำหนดเพิ่มเติมยาวเกินขนาดของรอบนี้ กรุณาแยกเป็นงานรอบถัดไป")
    instruction = store.add_sprint_instruction(project_id, active.sprint_id, req.role, req.message.strip())
    store.add_console_message(project_id, 'system', f"เก็บข้อกำหนดให้ {req.role} รอขั้นถัดไป: {req.message.strip()}", msg_type='system')
    await hub.broadcast("AGENT_WHISPER_RECEIVED", instruction)
    return {"status": "INSTRUCTION_QUEUED", "role": req.role, "instruction_id": instruction["instruction_id"],
            "message": "เก็บข้อกำหนดแล้ว จะนำไปใช้เมื่อ agent เริ่มขั้นถัดไป ไม่ได้แทรกกลางคำสั่งที่กำลังรัน"}

@router.get("/projects/{project_id}/sprints/{sprint_id}/attempts")
def get_sprint_attempts(project_id: str, sprint_id: str):
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    import json
    return [{**{key: value for key, value in attempt.items() if key != 'result_json'},
             'usage': json.loads(attempt['result_json'])} for attempt in store.get_attempts(sprint_id)]


@router.get("/projects/{project_id}/events")
def get_run_events(project_id: str, after: int = 0, limit: int = 200):
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return hub.journal.replay(after, project_id, limit)


@router.get("/projects/{project_id}/sprints/{sprint_id}/instructions")
def get_sprint_instructions(project_id: str, sprint_id: str):
    sprint = store.get_sprint(sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Sprint not found for this project")
    return store.get_sprint_instructions(sprint_id)

@router.post("/projects/{project_id}/directive")
async def send_directive(project_id: str, req: DirectiveRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if not runner.runtime_status()["available"]:
        raise HTTPException(status_code=503, detail=runner.runtime_status()["message"])
    item = sprint_queue.enqueue(
        project_id, req.directive,
        acceptance_criteria=req.acceptance_criteria, protected_paths=req.protected_paths,
    )
    await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "queue_id": item.queue_id})
    return {"status": "QUEUED", "project_id": project_id, "directive": req.directive, "queue_id": item.queue_id}

@router.post("/projects/{project_id}/sprints/pause")
async def pause_sprint(project_id: str):
    if not store.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not any(item.status == "RUNNING" for item in store.get_sprints(project_id)):
        raise HTTPException(status_code=409, detail="No active sprint to pause")
    orchestrator.pause_pipeline(project_id)
    return {"status": "PAUSE_REQUESTED", "message": "กำลังหยุด process และเก็บไฟล์; รอให้สถานะเป็น PAUSED ก่อน Resume"}


@router.post("/projects/{project_id}/sprints/abort")
async def abort_sprint(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    orchestrator.abort_pipeline(project_id)
    await hub.broadcast("PIPELINE_HALTED", {"project_id": project_id, "summary": "Sprint aborted by PM."})
    return {"status": "ABORTED", "project_id": project_id}

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

@router.get("/projects/{project_id}/git/patch")
def export_git_patch(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    patch = git_svc.get_patch(p.workspace_path)
    return Response(
        content=patch,
        media_type="text/x-diff",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-changes.patch"'}
    )

@router.get("/projects/{project_id}/git/remotes")
def get_project_git_remotes(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"remotes": git_svc.get_remotes(p.workspace_path)}

@router.post("/projects/{project_id}/git/remotes")
def set_project_git_remote(project_id: str, req: GitRemoteRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    res = git_svc.set_remote(p.workspace_path, req.name, req.url)
    return res

@router.post("/projects/{project_id}/git/push")
def push_project_git(project_id: str, req: GitPushPullRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return git_svc.git_push(p.workspace_path, remote=req.remote, branch=req.branch)

@router.post("/projects/{project_id}/git/pull")
def pull_project_git(project_id: str, req: GitPushPullRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return git_svc.git_pull(p.workspace_path, remote=req.remote, branch=req.branch)

@router.get("/projects/{project_id}/git/branches")
def list_project_git_branches(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"branches": git_svc.list_branches(p.workspace_path)}

@router.post("/projects/{project_id}/git/branches")
def create_project_git_branch(project_id: str, req: GitBranchRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return git_svc.create_branch(p.workspace_path, req.branch_name, checkout=bool(req.checkout))

@router.post("/projects/{project_id}/git/checkout")
def checkout_project_git_branch(project_id: str, req: GitCheckoutRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return git_svc.switch_branch(p.workspace_path, req.branch_name)

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
            "display_name": a.display_name, "persona": a.persona, "persona_source": a.persona_source,
            "equipped_skills": getattr(a, "equipped_skills", [])
        })
    return result

@router.get("/projects/{project_id}/skills/{role}")
def get_agent_skill(project_id: str, role: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    skill = skill_manager.get_skill(role, project_path=p.workspace_path)
    core = skill_manager.get_base_role_skill(role)
    identity = registered_agent(project_id, role)
    return {
        "name": skill.name,
        "title": skill.title,
        "description": skill.description,
        "allowed_tools": skill.allowed_tools,
        "triggers": skill.triggers,
        "tier": skill.tier,
        "instructions": skill.instructions,
        "raw_content": skill.raw_content,
        "file_path": skill.file_path,
        "core_role_playbook": {"name": core.name, "title": core.title, "instructions": core.instructions, "file_path": core.file_path},
        "project_rules_applied": skill_manager.get_project_role_skill(role, p.workspace_path) is not None,
        "diagnostics": dict(skill_manager.diagnostics),
        "role": identity.role, "display_name": identity.display_name, "persona": identity.persona, "persona_source": identity.persona_source,
    }

@router.put("/projects/{project_id}/skills/{role}")
def update_agent_skill(project_id: str, role: str, req: SkillUpdateRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    registered_agent(project_id, role)
    try:
        saved_path = skill_manager.save_custom_skill(project_path=p.workspace_path, role=role, content=req.content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    skill = skill_manager.get_skill(role, project_path=p.workspace_path)
    # Project rules apply independently of operational selection and live status.
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
    
    agent = registered_agent(project_id, role)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{role}' not found in project '{project_id}'")

    skill = required_skill(req.skill_name, p.workspace_path)
    updated_state = store.assign_agent_skill(
        project_id=project_id,
        role=role,
        skill_name=skill.name,
        skill_tier=skill.tier,
        skill_title=skill.title
    )
    equipped = list(agent.equipped_skills or [])
    if skill.name not in equipped:
        equipped.append(skill.name)
    store.set_agent_status(
        project_id=project_id,
        role=role,
        status=agent.status.value,
        thought=agent.thought,
        current_task_id=agent.current_task_id,
        last_tool_call=agent.last_tool_call,
        skill_name=skill.name,
        skill_tier=skill.tier,
        skill_title=skill.title,
        equipped_skills=equipped,
        skill_mode="MANUAL"
    )
    return {
        "status": "SUCCESS",
        "project_id": project_id,
        "role": role,
        "skill_name": updated_state.skill_name,
        "skill_tier": updated_state.skill_tier,
        "skill_title": updated_state.skill_title,
        "equipped_skills": equipped,
        "skill_mode": "MANUAL"
    }

@router.post("/projects/{project_id}/agents/{role}/skills/add")
def add_agent_skill(project_id: str, role: str, req: SkillAddRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    
    agent = registered_agent(project_id, role)
    skill = required_skill(req.skill_name, p.workspace_path)
    equipped = agent.equipped_skills or []
    if skill.name not in equipped:
        equipped.append(skill.name)
    
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
    
    registered_agent(project_id, role)
    agent = store.remove_equipped_skill(project_id, role, req.skill_name)
    return {"status": "SUCCESS", "equipped_skills": agent.equipped_skills, "skill_mode": agent.skill_mode}

@router.post("/projects/{project_id}/agents/{role}/skills/set-mode")
def set_agent_skill_mode(project_id: str, role: str, req: SetSkillModeRequest):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if req.mode not in ["AUTO", "MANUAL"]:
        raise HTTPException(status_code=400, detail="Mode must be AUTO or MANUAL")
    
    agent = registered_agent(project_id, role)
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

    if not req.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    if not runner.runtime_status()["available"]:
        raise HTTPException(status_code=503, detail=runner.runtime_status()["message"])
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
        # Directive dispatch requires EXPLICIT Ctrl+Enter (is_directive=True) or @all/@team mention.
        # Auto-detection via keyword matching was removed — it caused false positives on casual chat.
        is_directive_cmd = bool(
            getattr(req, "is_directive", False)   # Ctrl+Enter = explicit directive
            or target_role == "Team"              # @all / @team = broadcast directive
        )

        if is_directive_cmd:
            dispatch_text = (
                f"🚀 **Tech Lead Dispatch:** รับทราบคำสั่ง PM: \"{clean_message}\" — กำลังเริ่มรัน Sprint และระดมทีม (Architect, Developers, QA) ลงมือทันทีครับ!"
                if target_role != "Team"
                else f"📢 Broadcasting directive to full team: {clean_message}"
            )
            console_svc.add_message(
                project_id=project_id,
                sender="TechLead" if target_role != "Team" else "system",
                content=dispatch_text,
                msg_type="system"
            )
            await hub.broadcast("CONSOLE_MESSAGE", {
                "project_id": project_id,
                "sender": "TechLead" if target_role != "Team" else "system",
                "content": dispatch_text,
                "msg_type": "system"
            })
            item = sprint_queue.enqueue(project_id, clean_message)
            await hub.broadcast("QUEUE_UPDATED", {"project_id": project_id, "queue_id": item.queue_id})
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
                attachments=req.attachments,
                event_callback=hub.broadcast
            )

            if result.get("status") != "SUCCESS":
                raise RuntimeError(result.get("error") or result.get("response") or "AI failed")
            response_text = result.get("response", "")
            code_proposals = result.get("code_proposals", [])

            msg_type = "code_proposal" if code_proposals else "agent_response"

            agent_msg = console_svc.add_message(
                project_id=project_id,
                sender=target_role,
                content=response_text,
                msg_type=msg_type,
                role=target_role,
                code_proposals=code_proposals,
                active_skills=result.get("active_skills", [])
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
            store.set_agent_status(project_id, target_role, "BLOCKED", error_msg[:200])
            await hub.broadcast("AGENT_STATE_UPDATE", {"project_id": project_id, "role": target_role, "status": "BLOCKED", "thought": error_msg})

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
    if os.path.commonpath([real_workspace, real_target]) != real_workspace:
        raise HTTPException(status_code=403, detail="File path must be inside the project workspace")

    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(real_target), exist_ok=True)

        # Write the file
        with open(real_target, 'w', encoding='utf-8') as f:
            f.write(req.content)

        # Git add + commit
        commit_msg = req.commit_message or f"Apply code change: {os.path.basename(req.filepath)}"
        try:
            subprocess.run(["git", "add", real_target], cwd=p.workspace_path, capture_output=True, timeout=10)
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

    from app.services.verification import verify_workspace
    result = await verify_workspace(p.workspace_path)
    msg = console_svc.add_message(
        project_id=project_id, sender="QATester",
        content=f"Test run {result['status']}: `{result['command']}`",
        msg_type="qa_result", qa_results=result)
    await hub.broadcast("CONSOLE_MESSAGE", msg.to_dict())
    return result
