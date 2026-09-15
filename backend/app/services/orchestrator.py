import asyncio
import uuid
import time
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

    def abort_pipeline(self, project_id: str):
        """Signals the orchestrator to abort any active pipeline for this project."""
        self._aborted_projects.add(project_id)
        for req_id, (evt, holder) in list(self._pending_gates.items()):
            holder["decision"] = "REJECTED"
            evt.set()

    def resolve_gate(self, request_id: str, decision: str):
        """Called by the API when PM approves/rejects a gate. Unblocks the pipeline."""
        if request_id in self._pending_gates:
            event, holder = self._pending_gates[request_id]
            holder["decision"] = decision
            event.set()

    async def _wait_for_approval(self, request_id: str, timeout: float = 3600.0) -> str:
        """Block pipeline until PM resolves the approval gate or timeout."""
        event = asyncio.Event()
        holder = {"decision": "APPROVED"}  # default if timeout
        self._pending_gates[request_id] = (event, holder)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            holder["decision"] = "APPROVED"  # auto-approve on timeout
        finally:
            self._pending_gates.pop(request_id, None)
        return holder["decision"]

    async def execute_pm_directive(self, project_id: str, directive: str, event_callback=None) -> Dict[str, Any]:
        workspace = self.pm.get_project_workspace(project_id)
        project = self.store.get_project(project_id)
        if not project:
            raise KeyError(f"Project {project_id} not found")

        meta = self.store.get_project_metadata(project_id)

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

        async def check_and_handle_abort() -> Optional[Dict[str, Any]]:
            if project_id in self._aborted_projects:
                self._aborted_projects.discard(project_id)
                roles_to_reset = set(["TechLead", "Architect", "Designer", "BackendDev", "FrontendDev", "QATester", "Reviewer", "DocWriter"])
                if hasattr(self.store, "list_agents"):
                    try:
                        for a in self.store.list_agents(project_id):
                            roles_to_reset.add(a.role)
                    except Exception:
                        pass
                for r in roles_to_reset:
                    try:
                        self.store.set_agent_status(project_id, r, "IDLE", thought="Sprint aborted by PM.")
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

        if event_callback:
            await event_callback("SPRINT_STARTED", {
                "project_id": project_id,
                "sprint_id": sprint_id,
                "directive": directive
            })

        try:
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
            tl_res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="TechLead",
                prompt=f"Triage PM directive, assess project impact, and coordinate tasks with Architect: {directive}",
                workspace_path=workspace,
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
                await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "TechLead", "step_label": "Triage & Dispatch", "response": tl_notes[:600]})
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 1. Architect decomposes tasks
            await update_agent("Architect", "THINKING", f"Decomposing PM directive: {directive}")
            arch_prompt = (
                f"Analyze requirements and generate technical task breakdown for: {directive}\n\n"
                f"Tech Lead Guidance & Constraints:\n{tl_notes}"
            )
            t0_arch_res = time.time()

            arch_res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="Architect",
                prompt=arch_prompt,
                workspace_path=workspace,
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
                await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "Architect", "step_label": "Task Decomposition", "response": arch_plan[:600]})
            
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
            
            # Create initial tasks in state store linked to sprint_id
            t_ui = self.store.create_task(project_id, "Design UI and Tokens", "Designer", f"Design layout for: {directive}", sprint_id=sprint_id)
            t_fe = self.store.create_task(project_id, "Frontend Implementation", "FrontendDev", f"Build UI for: {directive}", sprint_id=sprint_id)
            t_be = self.store.create_task(project_id, "Backend & API Logic", "BackendDev", f"Implement server logic for: {directive}", sprint_id=sprint_id)
            t_qa = self.store.create_task(project_id, "Automated Verification", "QATester", "Run tests and verify quality", sprint_id=sprint_id)
            t_rev = self.store.create_task(project_id, "Code Review & Audit", "Reviewer", "Perform final code review and security audit", sprint_id=sprint_id)
            t_doc = self.store.create_task(project_id, "Documentation", "DocWriter", "Update project documentation and README", sprint_id=sprint_id)
            
            # Support custom specialists in project roster
            standard_roles = {"TechLead", "Architect", "Designer", "BackendDev", "FrontendDev", "QATester", "Reviewer", "DocWriter"}
            all_agents = self.store.list_agents(project_id) if hasattr(self.store, "list_agents") else []
            custom_agents = [a for a in all_agents if a.role not in standard_roles]
            custom_tasks = []
            for ca in custom_agents:
                t_custom = self.store.create_task(
                    project_id,
                    f"{ca.role} Implementation",
                    ca.role,
                    f"Apply specialist domain expertise ({ca.thought or ca.skill_title or ca.role}) for: {directive}",
                    sprint_id=sprint_id
                )
                custom_tasks.append((ca, t_custom))
    
            tasks_count = 6 + len(custom_tasks)
            self.store.update_sprint(sprint_id, tasks_count=tasks_count, total_tokens=total_tokens, backend_used=get_backend())
    
            if event_callback:
                await event_callback("TASKS_UPDATED", {"project_id": project_id})
    
            # 2. Approval Gate — truly blocks in Hybrid Mode (auto_pilot=False)
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            if not project.auto_pilot:
                approval = self.store.create_approval_request(
                    project_id=project_id,
                    gate_type="PLAN_APPROVAL",
                    summary=f"Architect planned {tasks_count} tasks for: {directive}"
                )
                if event_callback:
                    await event_callback("DECISION_GATE_OPEN", {
                        "project_id": project_id,
                        "request_id": approval.request_id,
                        "gate_type": "PLAN_APPROVAL",
                        "summary": approval.summary
                    })
    
                # *** BLOCKING WAIT — pipeline pauses here until PM resolves ***
                decision = await self._wait_for_approval(approval.request_id)
    
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
                    f"Task for Designer: Create styling tokens, design system variables, component layouts, and responsive specifications."
                )
                t0_des = time.time()
                res = await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role="Designer",
                    prompt=designer_prompt,
                    workspace_path=workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )
                record_res(res, role="Designer", duration=time.time() - t0_des)
                self.store.update_task_result(t_ui.task_id, res.get("response", "Design specifications ready"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "Designer", "UI Design & Tokens", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("Designer", "DONE", "Design specifications ready")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "Designer", "step_label": "UI Design & Tokens", "response": res.get("response", "")[:600]})
                return res
    
            async def run_backend():
                self.store.update_task_status(t_be.task_id, "IN_PROGRESS")
                await update_agent("BackendDev", "WORKING", "Implementing endpoints and data layer")
                backend_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Blueprint & API Contracts:\n{arch_plan}\n\n"
                    f"Task for BackendDev: Implement database models, schemas, and API endpoints according to the architecture."
                )
                t0_be = time.time()
                res = await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role="BackendDev",
                    prompt=backend_prompt,
                    workspace_path=workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )
                record_res(res, role="BackendDev", duration=time.time() - t0_be)
                self.store.update_task_result(t_be.task_id, res.get("response", "Backend endpoints complete"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "BackendDev", "API Implementation", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("BackendDev", "DONE", "Backend endpoints complete")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "BackendDev", "step_label": "API Implementation", "response": res.get("response", "")[:600]})
                return res
    
            async def run_custom_specialist(ca, task_item):
                self.store.update_task_status(task_item.task_id, "IN_PROGRESS")
                await update_agent(ca.role, "WORKING", f"Executing specialist tasks for: {directive}")
                custom_prompt = (
                    f"Sprint Directive: {directive}\n\n"
                    f"Architectural Blueprint:\n{arch_plan}\n\n"
                    f"Specialist Persona: {ca.thought or ca.skill_title or ca.role}\n\n"
                    f"Task for {ca.role}: Implement your domain-specific components matching the architectural requirements."
                )
                t0_ca = time.time()
                res = await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role=ca.role,
                    prompt=custom_prompt,
                    workspace_path=workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )
                record_res(res, role=ca.role, duration=time.time() - t0_ca)
                self.store.update_task_result(task_item.task_id, res.get("response", f"{ca.role} tasks complete"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, ca.role, "Specialist Tasks", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent(ca.role, "DONE", f"{ca.role} tasks complete")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": ca.role, "step_label": "Specialist Tasks", "response": res.get("response", "")[:600]})
                return res
    
            # Parallel dispatch: Designer + BackendDev + any Custom Specialists
            parallel_coros = [run_designer(), run_backend()] + [run_custom_specialist(ca, t) for ca, t in custom_tasks]
            parallel_results = await asyncio.gather(*parallel_coros)
            designer_res = parallel_results[0]
            backend_res = parallel_results[1]
    
            # Update Shared Blackboard with completed specifications
            sprint_context["design_specs"] = designer_res.get("response", "")
            sprint_context["backend_specs"] = backend_res.get("response", "")
            
            specialist_specs = ""
            if len(parallel_results) > 2:
                for idx, r in enumerate(parallel_results[2:]):
                    ca = custom_tasks[idx][0]
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
                    f"Task for FrontendDev: Build frontend components and pages connecting to backend endpoints using design tokens."
                )
                t0_fe = time.time()
                res = await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role="FrontendDev",
                    prompt=frontend_prompt,
                    workspace_path=workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )
                record_res(res, role="FrontendDev", duration=time.time() - t0_fe)
                self.store.update_task_result(t_fe.task_id, res.get("response", "Frontend code committed"), status="DONE")
                if hasattr(self.store, "save_agent_sprint_log"):
                    try:
                        self.store.save_agent_sprint_log(project_id, sprint_id, "FrontendDev", "UI Implementation", res.get("response", ""), res.get("tokens_used", 0))
                    except Exception: pass
                await update_agent("FrontendDev", "DONE", "Frontend code committed")
                if event_callback:
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "FrontendDev", "step_label": "UI Implementation", "response": res.get("response", "")[:600]})
                return res
    
            frontend_res = await run_frontend()
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 4. QA Tester with Self-Healing Loop (Max 3 retries) and full acceptance criteria
            self.store.update_task_status(t_qa.task_id, "TESTING")
            await update_agent("QATester", "TESTING", "Running test suite and regression checks")
            sprint_context["qa_criteria"] = (
                f"Sprint Directive: {directive}\n"
                f"Automated Test Command: {meta.get('test_command') or 'run test suite'}\n"
                f"Architect Acceptance Criteria:\n{arch_plan}"
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
                    f"Architect Acceptance Criteria:\n{arch_plan}\n\n"
                    f"Backend Changes:\n{sprint_context.get('backend_specs', '')[:1500]}\n\n"
                    f"Frontend Changes:\n{frontend_res.get('response', '')[:1500]}\n\n"
                    f"Specialist Specifications:\n{sprint_context.get('specialist_specs', '')[:1000]}\n\n"
                    f"Task for QATester: Execute unit and integration tests and verify against acceptance criteria. (Attempt {attempt}/{max_retries})"
                )
                t0_qa_res = time.time()

                qa_res = await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role="QATester",
                    prompt=qa_prompt,
                    workspace_path=workspace,
                    project_context=sprint_context,
                    event_callback=event_callback
                )

                record_res(qa_res, role="QATester", duration=time.time() - t0_qa_res)
                
                # Simulated failure handling or real error recovery with intelligent role routing
                if "FAIL" in qa_res.get("response", "") and attempt < max_retries:
                    qa_report = qa_res.get("response", "")
                    qa_lower = qa_report.lower()
                    
                    fe_keywords = [
                        "frontend", "ui", "ux", "css", "html", "jsx", "tsx", "component",
                        "react", "vue", "button", "layout", "browser", "dom", "vite", "tailwind", "client"
                    ]
                    be_keywords = [
                        "backend", "api", "endpoint", "database", "sql", "db", "server",
                        "router", "fastapi", "pydantic", "model", "migration", "500", "502"
                    ]
                    fe_hits = sum(1 for kw in fe_keywords if kw in qa_lower)
                    be_hits = sum(1 for kw in be_keywords if kw in qa_lower)
                    fix_role = "FrontendDev" if fe_hits > be_hits else "BackendDev"
                    target_task_id = t_fe.task_id if fix_role == "FrontendDev" else t_be.task_id
    
                    await update_agent("QATester", "BLOCKED", f"Test failures caught on attempt {attempt}. Dispatching fix to {fix_role}.")
                    await update_agent(fix_role, "WORKING", f"Self-healing: fixing code based on QA failure report (Attempt {attempt})")
                    fix_prompt = (
                        f"Sprint Directive: {directive}\n\n"
                        f"QA Failure Report:\n{qa_report}\n\n"
                        f"Task for {fix_role}: Fix all errors reported in QA test execution and ensure all tests pass."
                    )
                    t0_fix_res = time.time()

                    fix_res = await self.runner.dispatch_agent_task(
                        project_id=project_id,
                        role=fix_role,
                        prompt=fix_prompt,
                        workspace_path=workspace,
                        project_context=sprint_context,
                        event_callback=event_callback
                    )

                    record_res(fix_res, role=fix_role, duration=time.time() - t0_fix_res)
                    self.store.update_task_result(target_task_id, fix_res.get("response", f"{fix_role} self-healing fix applied"), status="DONE")
                    await update_agent(fix_role, "DONE", f"Self-healing fix applied by {fix_role}")
    
                    aborted = await check_and_handle_abort()
                    if aborted:
                        return aborted
                elif "FAIL" in qa_res.get("response", ""):
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
    
                # Create PM intervention gate
                qa_approval = self.store.create_approval_request(
                    project_id=project_id,
                    gate_type="QA_FAILURE_ESCALATION",
                    summary=f"All {max_retries} QA attempts failed for: {directive}. Approve to continue anyway, or Reject to halt."
                )
                if event_callback:
                    await event_callback("DECISION_GATE_OPEN", {
                        "project_id": project_id,
                        "request_id": qa_approval.request_id,
                        "gate_type": "QA_FAILURE_ESCALATION",
                        "summary": qa_approval.summary
                    })
    
                decision = await self._wait_for_approval(qa_approval.request_id)
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
                    await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "QATester", "step_label": "Test Verification", "response": qa_res.get("response", "")[:600]})
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # 5. Reviewer signs off with full sprint blackboard
            self.store.update_task_status(t_rev.task_id, "IN_PROGRESS")
            await update_agent("Reviewer", "REVIEWING", "Auditing security, diff quality, and writing release summary")
            rev_prompt = (
                f"Sprint Directive: {directive}\n\n"
                f"Architectural Plan:\n{arch_plan}\n\n"
                f"Backend Implementation:\n{sprint_context.get('backend_specs', '')[:2000]}\n\n"
                f"Frontend Implementation:\n{frontend_res.get('response', '')[:2000]}\n\n"
                f"Specialist Specifications:\n{sprint_context.get('specialist_specs', '')[:1000]}\n\n"
                f"QA Test Results:\n{qa_res.get('response', '')[:1000]}\n\n"
                f"Task for Reviewer: Perform final code review, verify git diff, audit security and quality, and create PM release notes."
            )
            t0_rev_res = time.time()

            rev_res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="Reviewer",
                prompt=rev_prompt,
                workspace_path=workspace,
                project_context=sprint_context,
                event_callback=event_callback
            )

            record_res(rev_res, role="Reviewer", duration=time.time() - t0_rev_res)
            self.store.update_task_result(t_rev.task_id, rev_res.get("response", "Release approved"), status="DONE")
            await update_agent("Reviewer", "DONE", "Release approved and documented")
            if event_callback:
                await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "Reviewer", "step_label": "Code Review & Release Notes", "response": rev_res.get("response", "")[:600]})
    
            if hasattr(self.store, "save_agent_sprint_log"):
                try:
                    self.store.save_agent_sprint_log(project_id, sprint_id, "Reviewer", "Code Review & Release Notes", rev_res.get("response", ""), rev_res.get("tokens_used", 0))
                except Exception: pass
    
            aborted = await check_and_handle_abort()
            if aborted:
                return aborted
    
            # DocWriter with full sprint blackboard
            self.store.update_task_status(t_doc.task_id, "IN_PROGRESS")
            await update_agent("DocWriter", "WORKING", "Updating project documentation and README")
            doc_prompt = (
                f"Sprint Directive: {directive}\n\n"
                f"Release Notes & Review:\n{rev_res.get('response', '')}\n\n"
                f"Task for DocWriter: Update project documentation, README, and user guides for completed sprint."
            )
            t0_doc_res = time.time()

            doc_res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="DocWriter",
                prompt=doc_prompt,
                workspace_path=workspace,
                project_context=sprint_context,
                event_callback=event_callback
            )

            record_res(doc_res, role="DocWriter", duration=time.time() - t0_doc_res)
            self.store.update_task_result(t_doc.task_id, doc_res.get("response", "Docs up to date"), status="DONE")
            await update_agent("DocWriter", "DONE", "Docs up to date")
            if hasattr(self.store, "save_agent_sprint_log"):
                try:
                    self.store.save_agent_sprint_log(project_id, sprint_id, "DocWriter", "Documentation Update", doc_res.get("response", ""), doc_res.get("tokens_used", 0))
                except Exception: pass
            if event_callback:
                await event_callback("AGENT_RESPONSE", {"project_id": project_id, "sprint_id": sprint_id, "role": "DocWriter", "step_label": "Documentation Update", "response": doc_res.get("response", "")[:600]})
    
            # Tech Lead wraps up sprint
            await update_agent("TechLead", "DONE", f"Sprint completed successfully: {directive}")
    
            release_summary = rev_res.get("response", "Sprint successfully completed by AI team!")
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
                "backend_used": get_backend()
            }

        except Exception as e:
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
                    self.store.set_agent_status(project_id, r, "IDLE", thought="Pipeline crashed")
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
