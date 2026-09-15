import asyncio
import uuid
import time
import os
from app.services.verification import verify_workspace
from app.services.pipeline_contracts import build_execution_plan, choose_fix_owner, parse_reviewer_verdict
from app.services.workspace_session import WorkspaceSession, changed_paths, flatten_changes, snapshot_workspace
from typing import Dict, Any, Optional
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.models.schemas import TaskStatus, AgentStatus, SprintRecord

class Orchestrator:
    def __init__(self, store: StateStore, project_manager: ProjectManager, agent_runner: AgentRunner):
        self.store = store
        self.pm = project_manager
        self.runner = agent_runner
        # Pending approval gates: { request_id: (asyncio.Event, decision_holder) }
        self._pending_gates: Dict[str, tuple] = {}
        self._aborted_projects: set = set()
        self._gate_projects = {}
        self._running_tasks = {}
        self._active_projects = set()

    def abort_pipeline(self, project_id: str):
        """Signals the orchestrator to abort any active pipeline for this project."""
        if project_id not in self._active_projects:
            return
        self._aborted_projects.add(project_id)
        for task in tuple(self._running_tasks.get(project_id, ())):
            if task is not asyncio.current_task():
                task.cancel()
        for req_id, (evt, holder) in list(self._pending_gates.items()):
            if self._gate_projects.get(req_id) == project_id:
                holder["decision"] = "REJECTED"
                evt.set()

    def resolve_gate(self, request_id: str, decision: str):
        """Called by the API when PM approves/rejects a gate. Unblocks the pipeline."""
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("Invalid approval decision")
        if request_id in self._pending_gates:
            event, holder = self._pending_gates[request_id]
            holder["decision"] = decision
            event.set()

    async def _wait_for_approval(self, request_id: str, timeout: float = 3600.0) -> str:
        """Block pipeline until PM resolves the approval gate or timeout."""
        event, holder = self._pending_gates.setdefault(request_id, (asyncio.Event(), {"decision": "REJECTED"}))
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            holder["decision"] = "REJECTED"  # A timeout is not PM approval
        finally:
            self._pending_gates.pop(request_id, None)
            self._gate_projects.pop(request_id, None)
            self.store.resolve_approval(request_id, holder["decision"])
        return holder["decision"]

    async def execute_pm_directive(self, project_id: str, directive: str, event_callback=None) -> Dict[str, Any]:
        workspace = self.pm.get_project_workspace(project_id)
        execution_workspace = workspace
        workspace_session = None
        workspace_committed = False
        project = self.store.get_project(project_id)
        if not project:
            raise KeyError(f"Project {project_id} not found")

        meta = self.store.get_project_metadata(project_id)

        broadcast = event_callback
        async def event_callback(event_type, data):
            data = {"timestamp": time.time(), **data}
            if event_type in {"AGENT_STATUS_CHANGE", "AGENT_THOUGHT_DELTA", "AGENT_PROGRESS"} and data.get("role"):
                state = self.store.get_agent_status(project_id, data["role"])
                self.store.set_agent_status(
                    project_id, data["role"], data.get("status") or (state.status if state else "IDLE"),
                    thought=data.get("thought") or data.get("message") or (state.thought if state else ""))
            if broadcast:
                await broadcast(event_type, data)
            content = None
            if event_type == "AGENT_RESPONSE":
                content = f"**{data.get('step_label', 'Result')}**\n\n{data.get('response', '')}"
            elif event_type == "AGENT_STATE_UPDATE" and data.get("status") != "DONE":
                content = data.get("thought")
            elif event_type == "EXECUTION_PLAN_READY":
                criteria = "\n".join(f"- {item}" for item in data.get("acceptance_criteria", []))
                content = f"{data.get('summary')}\nAgents: {', '.join(data.get('roles', []))}\n{criteria}"
            elif event_type in {"AGENT_EVIDENCE", "WORKSPACE_COMMITTED"}:
                paths = "\n".join(f"- {path}" for path in data.get("changed_files", [])) or "- ไม่มีไฟล์เปลี่ยน"
                content = f"{data.get('summary')}\n{paths}"
            elif event_type in {"SPRINT_STARTED", "PIPELINE_HALTED", "PIPELINE_REJECTED", "PIPELINE_COMPLETED", "DECISION_GATE_OPEN"}:
                content = data.get("summary") or f"เริ่ม Sprint: {data.get('directive', '')}"
            if content:
                message = self.store.add_console_message(
                    project_id, data.get("role", "system"), content,
                    msg_type="agent_response" if event_type == "AGENT_RESPONSE" else "system")
                if broadcast:
                    await broadcast("CONSOLE_MESSAGE", message)

        async def dispatch(**kwargs):
            if project_id in self._aborted_projects:
                raise RuntimeError("Sprint aborted by PM")
            require_changes = kwargs.pop("require_changes", False)
            before = await asyncio.to_thread(snapshot_workspace, kwargs["workspace_path"]) if require_changes and not self.runner.use_mock else None
            if require_changes:
                kwargs["prompt"] += (
                    "\n\nEvidence contract: make the smallest necessary workspace edits and report exact changed paths. "
                    "If the requested behavior is already fully implemented, make no cosmetic edit and include "
                    "`NO_CHANGES_REQUIRED:` followed by concrete file and verification evidence."
                )
            task = asyncio.create_task(self.runner.dispatch_agent_task(**kwargs))
            active = self._running_tasks.setdefault(project_id, set())
            active.add(task)
            try:
                result = await asyncio.wait_for(
                    task, timeout=max(1.0, float(os.environ.get("AGENT_TIMEOUT_SECONDS", "600"))) + 5)
            except asyncio.CancelledError:
                if project_id in self._aborted_projects:
                    raise RuntimeError("Sprint aborted by PM")
                raise
            finally:
                active.discard(task)
                if not active:
                    self._running_tasks.pop(project_id, None)
            if not result or result.get("status") != "SUCCESS":
                error = (result or {}).get("error") or (result or {}).get("response") or "No result returned"
                await update_agent(kwargs["role"], "BLOCKED", error)
                raise RuntimeError(f"{kwargs['role']}: {error}")
            if before is not None:
                after = await asyncio.to_thread(snapshot_workspace, kwargs["workspace_path"])
                evidence = changed_paths(before, after)
                paths = flatten_changes(evidence)
                result["changed_files"] = paths
                result["change_evidence"] = evidence
                await event_callback("AGENT_EVIDENCE", {
                    "project_id": project_id,
                    "role": kwargs["role"],
                    "changed_files": paths,
                    "summary": f"{len(paths)} file(s) changed" if paths else "No files changed",
                })
                if not paths and "NO_CHANGES_REQUIRED:" not in result.get("response", ""):
                    await update_agent(kwargs["role"], "BLOCKED", "Agent reported success without changing files or proving a no-op.")
                    raise RuntimeError(f"{kwargs['role']}: no workspace change evidence")
            return result

        # Helper to broadcast and persist agent state
        async def update_agent(role: str, status: str, thought: str = "", tool: str = None):
            self.store.set_agent_status(project_id, role, status, thought=thought, last_tool_call=tool)
            if event_callback:
                await event_callback("AGENT_STATE_UPDATE", {
                    "project_id": project_id,
                    "role": role,
                    "status": status,
                    "thought": thought,
                    "last_tool_call": tool
                })

        async def run_verification() -> Dict[str, Any]:
            if workspace_session is not None:
                await asyncio.to_thread(workspace_session.mount_dependencies)
            try:
                return await verify_workspace(execution_workspace)
            finally:
                if workspace_session is not None:
                    await asyncio.to_thread(workspace_session.unmount_dependencies)

        # Initialize Sprint tracking
        sprint_id = f"sprint-{uuid.uuid4().hex[:8]}"
        total_tokens = 0
        used_backends = set()
        tasks_count = 0

        def record_res(r, role=None, duration=0.0):
            nonlocal total_tokens
            if r and isinstance(r, dict):
                tokens = r.get("tokens_used", 0)
                total_tokens += tokens
                b = r.get("backend_used")
                if b:
                    used_backends.add(b)
                if role and hasattr(self.store, "record_agent_activity"):
                    try:
                        self.store.record_agent_activity(
                            project_id=project_id,
                            role=role,
                            action_type="sprint_task",
                            sprint_id=sprint_id,
                            tokens_used=tokens,
                            duration_seconds=duration,
                            status="SUCCESS" if r.get("status") != "FAILED" else "FAILED",
                            summary=r.get("response", "")[:200]
                        )
                    except Exception:
                        pass

        def get_backend():
            if not used_backends:
                return "mock"
            if len(used_backends) == 1:
                return next(iter(used_backends))
            return "+".join(sorted(used_backends))

        def task_output(result: Dict[str, Any], fallback: str) -> str:
            output = result.get("response", fallback)
            if "changed_files" in result:
                paths = result.get("changed_files", [])
                evidence = "\n".join(f"- {path}" for path in paths) if paths else "- no file changes (verified no-op)"
                output += f"\n\nChange evidence:\n{evidence}"
            return output

        async def check_and_handle_abort() -> Optional[Dict[str, Any]]:
            if project_id in self._aborted_projects:
                self._aborted_projects.discard(project_id)
                for task in self.store.get_sprint_tasks(sprint_id):
                    if task.status != "DONE":
                        self.store.update_task_result(task.task_id, "Sprint aborted by PM", status="FAILED")
                roles_to_reset = set(["TechLead", "Architect", "Designer", "BackendDev", "FrontendDev", "QATester", "Reviewer", "DocWriter"])
                if hasattr(self.store, "list_agents"):
                    try:
                        for a in self.store.list_agents(project_id):
                            roles_to_reset.add(a.role)
                    except Exception:
                        pass
                for r in roles_to_reset:
                    try:
                        await update_agent(r, "IDLE", "Sprint aborted by PM.")
                    except Exception:
                        pass
                self.store.update_sprint(
                    sprint_id,
                    status="FAILED",
                    completed_at=time.time(),
                    total_tokens=total_tokens,
                    backend_used=get_backend(),
                    tasks_count=tasks_count,
                    release_summary="Sprint aborted by PM."
                )
                if event_callback:
                    await event_callback("PIPELINE_HALTED", {
                        "project_id": project_id,
                        "directive": directive,
                        "summary": "Sprint aborted by PM."
                    })
                return {
                    "status": "ABORTED",
                    "project_id": project_id,
                    "directive": directive,
                    "sprint_id": sprint_id,
                    "total_tokens": total_tokens,
                    "backend_used": get_backend()
                }
            return None

        sprint_record = SprintRecord(
            sprint_id=sprint_id,
            project_id=project_id,
            directive=directive,
            status="RUNNING",
            total_tokens=0,
            backend_used="mock",
            started_at=time.time(),
            tasks_count=0
        )
        self.store.record_sprint(sprint_record)
        self._active_projects.add(project_id)

        if event_callback:
            await event_callback("SPRINT_STARTED", {
                "project_id": project_id,
                "sprint_id": sprint_id,
                "directive": directive
            })

        try:
            if not self.runner.use_mock:
                await event_callback("AGENT_PROGRESS", {
                    "project_id": project_id,
                    "role": "TechLead",
                    "message": "กำลังสร้าง staged workspace เพื่อป้องกันไฟล์ครึ่งงาน",
                })
                workspace_session = await asyncio.to_thread(WorkspaceSession, workspace)
                execution_workspace = str(workspace_session.workspace)

            # Build shared sprint context (Team Blackboard)
            sprint_context = dict(meta) if meta else {}
            sprint_context["sprint_directive"] = directive
    
            # Inject Project Memories if present
            if hasattr(self.store, "get_project_memories"):
                try:
                    memories = self.store.get_project_memories(project_id)
                    if memories:
                        sprint_context["project_memories"] = "\n".join(
                            f"- [{m.category.upper()}] {m.title}: {m.content}" for m in memories
                        )
                except Exception:
                    pass
    
            # 0. Tech Lead triages directive
            await update_agent("TechLead", "THINKING", f"Triaging PM directive: {directive}")
            t0_tl_res = time.time()
            tl_res = await dispatch(
                project_id=project_id,
                role="TechLead",
                prompt=(
                    f"Triage this PM directive against the existing repository: {directive}\n"
                    "State the user-visible outcome, constraints, likely affected areas, risks, explicit out-of-scope items, "
                    "and measurable acceptance criteria. Keep the implementation scope minimal."
                ),
                workspace_path=execution_workspace,
                project_context=sprint_context,
                event_callback=event_callback
            )
            record_res(tl_res, role="TechLead", duration=time.time() - t0_tl_res)
            tl_notes = tl_res.get("response", "")
            sprint_context["tech_lead_notes"] = tl_notes
            if hasattr(self.store, "save_agent_sprint_log"):
                try:
                    self.store.save_agent_sprint_log(project_id, sprint_id, "TechLead", "Triage & Dispatch", tl_notes, tl_res.get("tokens_used", 0))
                except Exception: pass
            await update_agent("TechLead", "DONE", "Triaged and delegated to Architect")
            if event_callback:
                await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "TechLead", "step_label": "Triage & Dispatch", "response": tl_notes})
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 1. Architect decomposes tasks
            await update_agent("Architect", "THINKING", f"Decomposing PM directive: {directive}")
            all_agents = self.store.list_agents(project_id) if hasattr(self.store, "list_agents") else []
            available_roles = "; ".join(
                f"{agent.role}: {agent.thought or agent.skill_title or 'project specialist'}"
                for agent in all_agents
            )
            arch_prompt = (
                f"Analyze requirements and generate technical task breakdown for: {directive}\n\n"
                f"Tech Lead Guidance & Constraints:\n{tl_notes}\n\n"
                "Finish with exactly one machine-readable block using this shape:\n"
                '<execution_plan>{"roles":["ROLE"],'
                '"acceptance_criteria":["observable result"]}</execution_plan>\n'
                f"Include only roles that are necessary. QA and Reviewer are added automatically.\n"
                f"Available project roles: {available_roles}"
            )
            t0_arch_res = time.time()

            arch_res = await dispatch(
                project_id=project_id,
                role="Architect",
                prompt=arch_prompt,
                workspace_path=execution_workspace,
                project_context=sprint_context,
                event_callback=event_callback
            )

            record_res(arch_res, role="Architect", duration=time.time() - t0_arch_res)
            arch_plan = arch_res.get("response", "")
            sprint_context["architect_plan"] = arch_plan
            if hasattr(self.store, "save_agent_sprint_log"):
                try:
                    self.store.save_agent_sprint_log(project_id, sprint_id, "Architect", "Task Decomposition", arch_plan, arch_res.get("tokens_used", 0))
                except Exception: pass
            await update_agent("Architect", "DONE", "Task breakdown complete")
            if event_callback:
                await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "Architect", "step_label": "Task Decomposition", "response": arch_plan})
            
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
            
            # Select only the agents this directive needs.
            standard_roles = {"TechLead", "Architect", "Designer", "BackendDev", "FrontendDev", "QATester", "Reviewer", "DocWriter"}
            custom_agents = [a for a in all_agents if a.role not in standard_roles]
            execution_plan = build_execution_plan(directive, arch_plan, meta, custom_agents)
            selected_roles = execution_plan["roles"]
            code_roles = [role for role in selected_roles if role not in {"Designer", "DocWriter"}]
            verification_required = bool(code_roles)
            sprint_context["execution_plan"] = execution_plan
            sprint_context["acceptance_criteria"] = "\n".join(
                f"- {item}" for item in execution_plan["acceptance_criteria"]
            )

            task_titles = {
                "Designer": "Design UI and Tokens",
                "FrontendDev": "Frontend Implementation",
                "BackendDev": "Backend & API Logic",
                "DocWriter": "Documentation",
                "QATester": "Automated Verification",
                "Reviewer": "Code Review & Audit",
            }
            task_by_role = {}
            for role in selected_roles + execution_plan["quality_roles"]:
                task_by_role[role] = self.store.create_task(
                    project_id, task_titles.get(role, f"{role} Implementation"), role,
                    f"Execute the approved scope for: {directive}", sprint_id=sprint_id,
                )
            t_ui = task_by_role.get("Designer")
            t_fe = task_by_role.get("FrontendDev")
            t_be = task_by_role.get("BackendDev")
            t_doc = task_by_role.get("DocWriter")
            t_qa = task_by_role["QATester"]
            t_rev = task_by_role["Reviewer"]

            custom_tasks = []
            for ca in custom_agents:
                if ca.role in selected_roles:
                    custom_tasks.append((ca, task_by_role[ca.role]))
    
            tasks_count = len(task_by_role)
            self.store.update_sprint(sprint_id, tasks_count=tasks_count, total_tokens=total_tokens, backend_used=get_backend())
    
            if event_callback:
                await event_callback("TASKS_UPDATED", {"project_id": project_id})
                await event_callback("EXECUTION_PLAN_READY", {
                    "project_id": project_id,
                    "sprint_id": sprint_id,
                    "roles": selected_roles + execution_plan["quality_roles"],
                    "acceptance_criteria": execution_plan["acceptance_criteria"],
                    "summary": f"เลือก {tasks_count} งานตามขอบเขตจริง",
                })
    
            # 2. Approval Gate — truly blocks in Hybrid Mode (auto_pilot=False)
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            if not project.auto_pilot:
                approval = self.store.create_approval_request(
                    project_id=project_id,
                    gate_type="PLAN_APPROVAL",
                    summary=(
                        f"แผนงาน {tasks_count} tasks: {directive}\n"
                        f"Agents: {', '.join(selected_roles + execution_plan['quality_roles'])}\n\n"
                        f"Acceptance criteria:\n{sprint_context['acceptance_criteria']}\n\n{arch_plan}"
                    )
                )
                self._pending_gates[approval.request_id] = (asyncio.Event(), {"decision": "REJECTED"})
                self._gate_projects[approval.request_id] = project_id
                if event_callback:
                    await event_callback("DECISION_GATE_OPEN", {
                        "project_id": project_id,
                        "request_id": approval.request_id,
                        "gate_type": "PLAN_APPROVAL",
                        "summary": approval.summary
                    })
    
                # *** BLOCKING WAIT — pipeline pauses here until PM resolves ***
                decision = await self._wait_for_approval(approval.request_id)
                await event_callback("DECISION_GATE_RESOLVED", {"project_id": project_id, "request_id": approval.request_id, "decision": decision})
                aborted = await check_and_handle_abort()
                if aborted:
                    return aborted
    
                if decision == "REJECTED":
                    self.store.update_sprint(
                        sprint_id,
                        status="REJECTED",
                        completed_at=time.time(),
                        total_tokens=total_tokens,
                        backend_used=get_backend(),
                        tasks_count=tasks_count,
                        release_summary="PM rejected the plan. Pipeline halted."
                    )
                    if event_callback:
                        await event_callback("PIPELINE_REJECTED", {
                            "project_id": project_id,
                            "directive": directive,
                            "summary": "PM rejected the plan. Pipeline halted."
                        })
                    return {
                        "status": "REJECTED",
                        "project_id": project_id,
                        "directive": directive,
                        "sprint_id": sprint_id,
                        "total_tokens": total_tokens,
                        "backend_used": get_backend()
                    }
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 3. Designer, Backend Dev, and Custom Specialists execute in parallel
            async def run_designer():
                self.store.update_task_status(t_ui.task_id, "IN_PROGRESS")
                await update_agent("Designer", "WORKING", "Creating styling tokens and responsive layout")
                designer_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Blueprint:\n{arch_plan}\n\n"
                    "Task for Designer: Inspect the existing design language and produce only the UI behavior, states, "
                    "responsive rules, and accessibility constraints needed by this directive. Preserve established styling."
                )
                t0_des = time.time()
                res = await dispatch(
                    project_id=project_id,
                    role="Designer",
                    prompt=designer_prompt,
                    workspace_path=execution_workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )
                record_res(res, role="Designer", duration=time.time() - t0_des)
                self.store.update_task_result(t_ui.task_id, task_output(res, "Design specifications ready"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "Designer", "UI Design & Tokens", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("Designer", "DONE", "Design specifications ready")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "Designer", "step_label": "UI Design & Tokens", "response": res.get("response", "")})
                return res
    
            async def run_backend():
                self.store.update_task_status(t_be.task_id, "IN_PROGRESS")
                await update_agent("BackendDev", "WORKING", "Implementing endpoints and data layer")
                backend_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Blueprint & API Contracts:\n{arch_plan}\n\n"
                    "Task for BackendDev: Inspect the affected code and implement only the approved backend behavior and tests. "
                    "Do not create a database, schema, service, or endpoint unless the plan specifically requires it."
                )
                t0_be = time.time()
                res = await dispatch(
                    project_id=project_id,
                    role="BackendDev",
                    prompt=backend_prompt,
                    workspace_path=execution_workspace,
                    project_context=sprint_context,
                    event_callback=event_callback,
                    require_changes=True,
                )
                record_res(res, role="BackendDev", duration=time.time() - t0_be)
                self.store.update_task_result(t_be.task_id, task_output(res, "Backend endpoints complete"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "BackendDev", "API Implementation", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("BackendDev", "DONE", "Backend endpoints complete")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "BackendDev", "step_label": "API Implementation", "response": res.get("response", "")})
                return res
    
            async def run_custom_specialist(ca, task_item):
                self.store.update_task_status(task_item.task_id, "IN_PROGRESS")
                await update_agent(ca.role, "WORKING", f"Executing specialist tasks for: {directive}")
                custom_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Blueprint:\n{arch_plan}\n\n"
                    f"Specialist Persona: {ca.thought or ca.skill_title or ca.role}\n\n"
                    f"Task for {ca.role}: Implement only the specialist work explicitly required by the plan; preserve unrelated behavior."
                )
                t0_ca = time.time()
                res = await dispatch(
                    project_id=project_id,
                    role=ca.role,
                    prompt=custom_prompt,
                    workspace_path=execution_workspace,
                    project_context=sprint_context,
                    event_callback=event_callback,
                    require_changes=True,
                )
                record_res(res, role=ca.role, duration=time.time() - t0_ca)
                self.store.update_task_result(task_item.task_id, task_output(res, f"{ca.role} tasks complete"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, ca.role, "Specialist Tasks", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent(ca.role, "DONE", f"{ca.role} tasks complete")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": ca.role, "step_label": "Specialist Tasks", "response": res.get("response", "")})
                return res
    
            # Run independent initial work concurrently only in simulation. Real
            # writers are serialized even inside the staged workspace so one
            # agent cannot overwrite another agent's edits.
            initial_jobs = []
            if t_ui:
                initial_jobs.append(("Designer", run_designer()))
            if t_be:
                initial_jobs.append(("BackendDev", run_backend()))
            initial_jobs.extend((ca.role, run_custom_specialist(ca, task)) for ca, task in custom_tasks)
            parallel_coros = [job for _role, job in initial_jobs]
            if self.runner.use_mock:
                parallel_results = await asyncio.gather(*parallel_coros, return_exceptions=True)
            else:
                # Every agent writes the same checkout. Serialize writers to avoid lost edits.
                parallel_results = []
                try:
                    for coro in parallel_coros:
                        parallel_results.append(await coro)
                finally:
                    for coro in parallel_coros:
                        coro.close()
            for result in parallel_results:
                if isinstance(result, BaseException):
                    raise result
            results_by_role = {role: result for (role, _job), result in zip(initial_jobs, parallel_results)}
            designer_res = results_by_role.get("Designer", {"response": "Not required"})
            backend_res = results_by_role.get("BackendDev", {"response": "Not required"})
    
            # Update Shared Blackboard with completed specifications
            sprint_context["design_specs"] = designer_res.get("response", "")
            sprint_context["backend_specs"] = backend_res.get("response", "")
            
            specialist_specs = ""
            for ca, _task in custom_tasks:
                r = results_by_role.get(ca.role, {})
                specialist_specs += f"--- {ca.role} Specs ---\n{r.get('response', '')}\n\n"
            sprint_context["specialist_specs"] = specialist_specs
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # FrontendDev runs with full knowledge of Architect plan, Backend contracts, and Design tokens
            async def run_frontend():
                self.store.update_task_status(t_fe.task_id, "IN_PROGRESS")
                await update_agent("FrontendDev", "WORKING", "Building components and pages")
                frontend_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Blueprint:\n{arch_plan}\n\n"
                    f"Completed Backend API Contracts:\n{sprint_context.get('backend_specs', '')}\n\n"
                    f"Completed Design Tokens & Layout:\n{sprint_context.get('design_specs', '')}\n\n"
                    f"Specialist Specifications:\n{sprint_context.get('specialist_specs', '')}\n\n"
                    "Task for FrontendDev: Inspect the affected UI and implement only the approved behavior and tests. "
                    "Reuse existing components and APIs; do not add pages or integrations outside this plan."
                )
                t0_fe = time.time()
                res = await dispatch(
                    project_id=project_id,
                    role="FrontendDev",
                    prompt=frontend_prompt,
                    workspace_path=execution_workspace,
                    project_context=sprint_context,
                    event_callback=event_callback,
                    require_changes=True,
                )
                record_res(res, role="FrontendDev", duration=time.time() - t0_fe)
                self.store.update_task_result(t_fe.task_id, task_output(res, "Frontend code committed"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "FrontendDev", "UI Implementation", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("FrontendDev", "DONE", "Frontend code committed")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "FrontendDev", "step_label": "UI Implementation", "response": res.get("response", "")})
                return res
    
            frontend_res = await run_frontend() if t_fe else {"response": "Not required", "tokens_used": 0}

            # Documentation is part of the deliverable and therefore runs
            # before QA and review so its edits are covered by both gates.
            doc_res = {"response": "Documentation update not required", "tokens_used": 0}
            if t_doc:
                self.store.update_task_status(t_doc.task_id, "IN_PROGRESS")
                await update_agent("DocWriter", "WORKING", "Updating project documentation and README")
                doc_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Plan:\n{arch_plan}\n\n"
                    f"Backend Implementation:\n{sprint_context.get('backend_specs', '')[:1500]}\n\n"
                    f"Frontend Implementation:\n{frontend_res.get('response', '')[:1500]}\n\n"
                    "Task for DocWriter: Update only documentation affected by the completed implementation."
                )
                t0_doc_res = time.time()
                doc_res = await dispatch(
                    project_id=project_id, role="DocWriter", prompt=doc_prompt,
                    workspace_path=execution_workspace, project_context=sprint_context,
                    event_callback=event_callback, require_changes=True,
                )
                record_res(doc_res, role="DocWriter", duration=time.time() - t0_doc_res)
                self.store.update_task_result(t_doc.task_id, task_output(doc_res, "Docs up to date"), status="DONE")
                await update_agent("DocWriter", "DONE", "Docs up to date")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "DocWriter", "Documentation Update", doc_res.get("response", ""), doc_res.get("tokens_used", 0))
                    except Exception:
                        pass
                await event_callback("AGENT_RESPONSE", {
                    "project_id": project_id, "sprint_id": sprint_id, "role": "DocWriter",
                    "step_label": "Documentation Update", "response": doc_res.get("response", ""),
                })
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 4. QA Tester with Self-Healing Loop (Max 3 retries) and full acceptance criteria
            self.store.update_task_status(t_qa.task_id, "TESTING")
            await update_agent("QATester", "TESTING", "Running test suite and regression checks")
            sprint_context["qa_criteria"] = (
                f"Sprint Directive: {directive}\n"
                f"Automated Test Command: {meta.get('test_command') or 'run test suite'}\n"
                f"Architect Acceptance Criteria:\n{sprint_context['acceptance_criteria']}"
            )
            
            max_retries = 3
            tests_passed = False
            qa_res: Dict[str, Any] = {"response": "Automated verification pending", "tokens_used": 0, "status": "PENDING"}
            for attempt in range(1, max_retries + 1):
                aborted = await check_and_handle_abort()
                if aborted:
                    return aborted
    
                qa_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Automated Test Command: {meta.get('test_command') or 'run test suite'}\n\n"
                    f"Architect Acceptance Criteria:\n{sprint_context['acceptance_criteria']}\n\n"
                    f"Backend Changes:\n{sprint_context.get('backend_specs', '')[:1500]}\n\n"
                    f"Frontend Changes:\n{frontend_res.get('response', '')[:1500]}\n\n"
                    f"Specialist Specifications:\n{sprint_context.get('specialist_specs', '')[:1000]}\n\n"
                    f"Task for QATester: Inspect test coverage and acceptance risks without editing files. "
                    f"The orchestrator will run deterministic checks after this analysis. (Attempt {attempt}/{max_retries})"
                )
                t0_qa_res = time.time()

                qa_res = await dispatch(
                    project_id=project_id,
                    role="QATester",
                    prompt=qa_prompt,
                    workspace_path=execution_workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )

                record_res(qa_res, role="QATester", duration=time.time() - t0_qa_res)
                
                if self.runner.use_mock:
                    qa_failed = "fail" in qa_res.get("response", "").lower()
                else:
                    await update_agent("QATester", "TESTING", "กำลังตรวจผลด้วยชุดทดสอบจริง")
                    await event_callback("AGENT_PROGRESS", {"project_id": project_id, "role": "QATester", "message": "กำลังรันชุดทดสอบจริงและตรวจ exit code"})
                    verification = await run_verification()
                    aborted = await check_and_handle_abort()
                    if aborted:
                        return aborted
                    qa_failed = verification["status"] != "PASSED" and not (
                        verification["status"] == "NOT_RUN" and not verification_required
                    )
                    checks_summary = ", ".join(
                        f"{check['name']}={check['status']}" for check in verification.get("checks", [])
                    ) or "no checks discovered"
                    qa_res["response"] += (
                        f"\n\nVerification: {verification['status']}\n"
                        f"Checks: {checks_summary}\n"
                        f"Command: {verification['command']}\nExit code: {verification['exit_code']}\n"
                        f"{verification['stdout']}\n{verification['stderr']}"
                    )
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "role": "QATester", "step_label": f"Verification {attempt}/{max_retries}", "response": qa_res["response"]})

                if qa_failed and attempt < max_retries:
                    qa_report = qa_res.get("response", "")
                    repair_roles = [role for role in code_roles if role in task_by_role]
                    if not repair_roles:
                        break
                    fix_role = choose_fix_owner(qa_report, repair_roles)
                    target_task_id = task_by_role[fix_role].task_id
    
                    await update_agent("QATester", "BLOCKED", f"Test failures caught on attempt {attempt}. Dispatching fix to {fix_role}.")
                    await update_agent(fix_role, "WORKING", f"Self-healing: fixing code based on QA failure report (Attempt {attempt})")
                    fix_prompt = (
                        f"Sprint Directive: {directive}\n\n"
                        f"QA Failure Report:\n{qa_report}\n\n"
                        f"Task for {fix_role}: Fix all errors reported in QA test execution and ensure all tests pass."
                    )
                    t0_fix_res = time.time()

                    fix_res = await dispatch(
                        project_id=project_id,
                        role=fix_role,
                        prompt=fix_prompt,
                        workspace_path=execution_workspace,
                        project_context=sprint_context,
                        event_callback=event_callback,
                        require_changes=True,
                    )

                    record_res(fix_res, role=fix_role, duration=time.time() - t0_fix_res)
                    self.store.update_task_result(target_task_id, task_output(fix_res, f"{fix_role} self-healing fix applied"), status="DONE")
                    await update_agent(fix_role, "DONE", f"Self-healing fix applied by {fix_role}")
    
                    aborted = await check_and_handle_abort()
                    if aborted:
                        return aborted
                elif qa_failed:
                    # Final attempt also failed — escalate to PM
                    tests_passed = False
                    break
                else:
                    tests_passed = True
                    break
    
            if not tests_passed:
                # All retries exhausted — escalate to PM Decision Gate
                self.store.update_task_result(t_qa.task_id, qa_res.get("response", "Tests failed after retries"), status="FAILED")
                await update_agent("QATester", "BLOCKED", f"Tests failed after {max_retries} attempts. Escalating to PM.")
    
                if event_callback:
                    await event_callback("QA_ESCALATION", {
                        "project_id": project_id,
                        "message": f"QA failed after {max_retries} self-healing attempts. PM intervention required."
                    })
    
                # Auto-pilot fails fast. Hybrid mode can explicitly accept the
                # risk instead of leaving an unattended sprint waiting forever.
                decision = "REJECTED"
                if not project.auto_pilot:
                    qa_approval = self.store.create_approval_request(
                        project_id=project_id,
                        gate_type="QA_FAILURE_ESCALATION",
                        summary=f"All {max_retries} QA attempts failed for: {directive}. Approve to continue anyway, or Reject to halt."
                    )
                    self._pending_gates[qa_approval.request_id] = (asyncio.Event(), {"decision": "REJECTED"})
                    self._gate_projects[qa_approval.request_id] = project_id
                    await event_callback("DECISION_GATE_OPEN", {
                        "project_id": project_id, "request_id": qa_approval.request_id,
                        "gate_type": "QA_FAILURE_ESCALATION", "summary": qa_approval.summary,
                    })
                    decision = await self._wait_for_approval(qa_approval.request_id)
                    await event_callback("DECISION_GATE_RESOLVED", {
                        "project_id": project_id, "request_id": qa_approval.request_id, "decision": decision,
                    })
                aborted = await check_and_handle_abort()
                if aborted:
                    return aborted
                if decision == "REJECTED":
                    await update_agent("TechLead", "BLOCKED", f"Pipeline halted by PM due to QA failures: {directive}")
                    self.store.update_sprint(
                        sprint_id,
                        status="FAILED",
                        completed_at=time.time(),
                        total_tokens=total_tokens,
                        backend_used=get_backend(),
                        tasks_count=tasks_count,
                        release_summary="PM halted pipeline due to QA failures."
                    )
                    if event_callback:
                        await event_callback("PIPELINE_HALTED", {
                            "project_id": project_id,
                            "directive": directive,
                            "summary": "PM halted pipeline due to QA failures."
                        })
                    return {
                        "status": "HALTED_QA_FAILURE",
                        "project_id": project_id,
                        "directive": directive,
                        "sprint_id": sprint_id,
                        "total_tokens": total_tokens,
                        "backend_used": get_backend()
                    }
            else:
                self.store.update_task_result(t_qa.task_id, qa_res.get("response", "All automated verification checks passed ✅"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "QATester", "Test Verification", qa_res.get("response", ""), qa_res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("QATester", "DONE", "All automated verification checks passed ✅")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "QATester", "step_label": "Test Verification", "response": qa_res.get("response", "")})
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 5. Reviewer signs off with full sprint blackboard
            staged_evidence = await asyncio.to_thread(workspace_session.changes) if workspace_session is not None else {"added": [], "modified": [], "deleted": []}
            staged_paths = flatten_changes(staged_evidence)
            staged_diff = await asyncio.to_thread(workspace_session.review_diff) if workspace_session is not None else "Unavailable in simulation"
            self.store.update_task_status(t_rev.task_id, "IN_PROGRESS")
            await update_agent("Reviewer", "REVIEWING", "Auditing security, diff quality, and writing release summary")
            rev_prompt = (
                f"Sprint Directive: {directive}\n\n"
                f"Architectural Plan:\n{arch_plan}\n\n"
                f"Backend Implementation:\n{sprint_context.get('backend_specs', '')[:2000]}\n\n"
                f"Frontend Implementation:\n{frontend_res.get('response', '')[:2000]}\n\n"
                f"Documentation:\n{doc_res.get('response', '')[:1000]}\n\n"
                f"Specialist Specifications:\n{sprint_context.get('specialist_specs', '')[:1000]}\n\n"
                f"QA Test Results:\n{qa_res.get('response', '')[:1000]}\n\n"
                f"Changed Files ({len(staged_paths)}):\n" + "\n".join(f"- {path}" for path in staged_paths[:200]) + "\n\n"
                f"Unified Diff (bounded):\n{staged_diff}\n\n"
                "Task for Reviewer: Inspect the actual workspace and diff, verify every acceptance criterion, "
                "audit security and maintainability, and write release notes. Finish with exactly one block:\n"
                '<review_verdict>{"verdict":"APPROVED|CHANGES_REQUESTED|BLOCKED",'
                '"findings":["specific finding with file path"],"owners":["FrontendDev|BackendDev|DocWriter"]}</review_verdict>'
            )
            t0_rev_res = time.time()

            rev_res = await dispatch(
                project_id=project_id,
                role="Reviewer",
                prompt=rev_prompt,
                workspace_path=execution_workspace,
                project_context=sprint_context,
                event_callback=event_callback
            )

            record_res(rev_res, role="Reviewer", duration=time.time() - t0_rev_res)
            verdict = {"verdict": "APPROVED", "findings": [], "owners": []} if self.runner.use_mock else parse_reviewer_verdict(rev_res.get("response", ""))
            await event_callback("AGENT_RESPONSE", {
                "project_id": project_id, "sprint_id": sprint_id, "role": "Reviewer",
                "step_label": "Code Review 1", "response": rev_res.get("response", ""),
            })

            # One bounded repair pass turns actionable review feedback into a
            # fix while preserving a hard gate for BLOCKED or malformed output.
            if verdict["verdict"] == "CHANGES_REQUESTED":
                findings = "; ".join(str(item) for item in verdict.get("findings", [])) or "Reviewer requested changes"
                writer_roles = [role for role in selected_roles if role != "Designer" and role in task_by_role]
                requested_owners = [role for role in verdict.get("owners", []) if role in writer_roles]
                if not requested_owners and writer_roles:
                    requested_owners = [choose_fix_owner(findings, writer_roles)]
                if not requested_owners:
                    raise RuntimeError(f"Reviewer CHANGES_REQUESTED without an available owner: {findings}")

                for owner in list(dict.fromkeys(requested_owners))[:3]:
                    await update_agent(owner, "WORKING", "Applying reviewer feedback")
                    repair_res = await dispatch(
                        project_id=project_id,
                        role=owner,
                        prompt=(
                            f"Sprint Directive: {directive}\n\nReviewer Findings:\n{findings}\n\n"
                            "Fix only these findings, add or update focused tests when applicable, and report the exact files changed."
                        ),
                        workspace_path=execution_workspace,
                        project_context=sprint_context,
                        event_callback=event_callback,
                        require_changes=True,
                    )
                    record_res(repair_res, role=owner)
                    self.store.update_task_result(
                        task_by_role[owner].task_id,
                        task_output(repair_res, f"{owner} reviewer repair applied"),
                        status="DONE",
                    )
                    await update_agent(owner, "DONE", "Reviewer feedback applied")

                review_verification = await run_verification() if not self.runner.use_mock else {"status": "PASSED", "checks": []}
                aborted = await check_and_handle_abort()
                if aborted:
                    return aborted
                review_failed = review_verification["status"] != "PASSED" and not (
                    review_verification["status"] == "NOT_RUN" and not verification_required
                )
                if review_failed:
                    raise RuntimeError(f"Reviewer repair verification failed: {review_verification['status']}")

                staged_diff = await asyncio.to_thread(workspace_session.review_diff) if workspace_session is not None else "Unavailable in simulation"
                second_prompt = (
                    f"{rev_prompt}\n\nPrevious findings:\n{findings}\n\n"
                    f"Post-repair verification: {review_verification['status']}\n"
                    f"Updated unified diff:\n{staged_diff}\n\n"
                    "Review the repaired result and return a fresh review_verdict block."
                )
                t0_second_review = time.time()
                rev_res = await dispatch(
                    project_id=project_id, role="Reviewer", prompt=second_prompt,
                    workspace_path=execution_workspace, project_context=sprint_context,
                    event_callback=event_callback,
                )
                record_res(rev_res, role="Reviewer", duration=time.time() - t0_second_review)
                verdict = {"verdict": "APPROVED", "findings": [], "owners": []} if self.runner.use_mock else parse_reviewer_verdict(rev_res.get("response", ""))
                await event_callback("AGENT_RESPONSE", {
                    "project_id": project_id, "sprint_id": sprint_id, "role": "Reviewer",
                    "step_label": "Code Review 2", "response": rev_res.get("response", ""),
                })

            if verdict["verdict"] != "APPROVED":
                findings = "; ".join(str(item) for item in verdict.get("findings", [])) or "No actionable findings supplied"
                self.store.update_task_result(t_rev.task_id, rev_res.get("response", findings), status="FAILED")
                await update_agent("Reviewer", "BLOCKED", f"Release blocked: {findings}")
                raise RuntimeError(f"Reviewer {verdict['verdict']}: {findings}")
            self.store.update_task_result(t_rev.task_id, rev_res.get("response", "Release approved"), status="DONE")
            await update_agent("Reviewer", "DONE", "Release approved")
    
            if hasattr(self.store, "save_agent_sprint_log"):
                try:
                    self.store.save_agent_sprint_log(project_id, sprint_id, "Reviewer", "Code Review & Release Notes", rev_res.get("response", ""), rev_res.get("tokens_used", 0))
                except Exception: pass
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            final_verification = None
            workspace_changes = {"added": [], "modified": [], "deleted": []}
            if not self.runner.use_mock:
                await update_agent("QATester", "TESTING", "Running final verification after review")
                final_verification = await run_verification()
                final_checks = ", ".join(
                    f"{check['name']}={check['status']}" for check in final_verification.get("checks", [])
                ) or "no checks discovered"
                await event_callback("AGENT_RESPONSE", {
                    "project_id": project_id, "sprint_id": sprint_id, "role": "QATester",
                    "step_label": "Final Verification",
                    "response": f"Final verification: {final_verification['status']}\n{final_checks}",
                })
                aborted = await check_and_handle_abort()
                if aborted:
                    return aborted
                final_failed = final_verification["status"] != "PASSED" and not (
                    final_verification["status"] == "NOT_RUN" and not verification_required
                )
                if tests_passed and final_failed:
                    raise RuntimeError(f"Final verification failed: {final_verification['status']}")

                workspace_changes = await asyncio.to_thread(workspace_session.commit)
                workspace_committed = True
                await event_callback("WORKSPACE_COMMITTED", {
                    "project_id": project_id,
                    "sprint_id": sprint_id,
                    "changed_files": flatten_changes(workspace_changes),
                    "summary": f"นำ {len(flatten_changes(workspace_changes))} ไฟล์จาก staged workspace มาใช้แล้ว",
                })

            # Tech Lead wraps up sprint
            await update_agent("TechLead", "DONE", f"Sprint completed successfully: {directive}")
    
            release_summary = rev_res.get("response", "Sprint successfully completed by AI team!")
            if not tests_passed:
                release_summary = "⚠️ PM allowed continuation with unverified/failing tests.\n\n" + release_summary
            self.store.update_sprint(
                sprint_id,
                status="COMPLETED",
                completed_at=time.time(),
                total_tokens=total_tokens,
                backend_used=get_backend(),
                tasks_count=tasks_count,
                release_summary=release_summary
            )
    
            if event_callback:
                await event_callback("PIPELINE_COMPLETED", {
                    "project_id": project_id,
                    "directive": directive,
                    "summary": release_summary,
                    "sprint_id": sprint_id,
                    "total_tokens": total_tokens,
                    "backend_used": get_backend(),
                    "tasks_count": tasks_count
                })
    
            return {
                "status": "COMPLETED",
                "project_id": project_id,
                "directive": directive,
                "sprint_id": sprint_id,
                "total_tokens": total_tokens,
                "backend_used": get_backend(),
                "selected_roles": selected_roles + execution_plan["quality_roles"],
                "changed_files": flatten_changes(workspace_changes),
            }

        except Exception as e:
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
            for task in self.store.get_sprint_tasks(sprint_id):
                if task.status != "DONE":
                    self.store.update_task_result(task.task_id, f"Stopped: {e}", status="FAILED")
            import traceback
            error_msg = f"Pipeline crashed: {str(e)}\n{traceback.format_exc()}"
            print(f"Pipeline crashed: {e}")
            roles_to_reset = set(["TechLead", "Architect", "Designer", "BackendDev", "FrontendDev", "QATester", "Reviewer", "DocWriter"])
            if hasattr(self.store, "list_agents"):
                try:
                    for a in self.store.list_agents(project_id):
                        roles_to_reset.add(a.role)
                except Exception:
                    pass
            for r in roles_to_reset:
                try:
                    await update_agent(r, "BLOCKED", f"Pipeline stopped: {e}")
                except Exception:
                    pass
            try:
                self.store.update_sprint(
                    sprint_id,
                    status="FAILED",
                    completed_at=time.time(),
                    total_tokens=total_tokens,
                    backend_used=get_backend(),
                    tasks_count=tasks_count,
                    release_summary=f"Pipeline crashed: {str(e)}"
                )
            except Exception:
                pass
            if event_callback:
                try:
                    await event_callback("PIPELINE_HALTED", {
                        "project_id": project_id,
                        "directive": directive,
                        "summary": f"Pipeline crashed: {str(e)}"
                    })
                except Exception:
                    pass
            return {
                "status": "FAILED",
                "project_id": project_id,
                "directive": directive,
                "sprint_id": sprint_id,
                "error": str(e),
                "total_tokens": total_tokens,
                "backend_used": get_backend()
            }
        finally:
            if workspace_session is not None:
                if not workspace_committed:
                    for task in self.store.get_sprint_tasks(sprint_id):
                        previous = task.result_output or "Task did not complete."
                        if "Staged changes discarded" not in previous:
                            previous += "\n\nStaged changes discarded because the sprint did not pass every gate."
                        self.store.update_task_result(task.task_id, previous, status="FAILED")
                workspace_session.close()
            self._active_projects.discard(project_id)
