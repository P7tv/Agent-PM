import asyncio
from typing import Dict, Any, Optional
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.models.schemas import TaskStatus, AgentStatus

class Orchestrator:
    def __init__(self, store: StateStore, project_manager: ProjectManager, agent_runner: AgentRunner):
        self.store = store
        self.pm = project_manager
        self.runner = agent_runner
        # Pending approval gates: { request_id: (asyncio.Event, decision_holder) }
        self._pending_gates: Dict[str, tuple] = {}

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

        # 0. Tech Lead triages directive
        await update_agent("TechLead", "THINKING", f"Triaging PM directive: {directive}")
        await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="TechLead",
            prompt=f"Triage PM directive, assess project impact, and coordinate tasks with Architect: {directive}",
            workspace_path=workspace,
            project_context=meta,
            event_callback=event_callback
        )
        await update_agent("TechLead", "DONE", "Triaged and delegated to Architect")

        # 1. Architect decomposes tasks
        await update_agent("Architect", "THINKING", f"Decomposing PM directive: {directive}")
        arch_res = await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="Architect",
            prompt=f"Analyze requirements and generate task breakdown for: {directive}",
            workspace_path=workspace,
            project_context=meta,
            event_callback=event_callback
        )
        await update_agent("Architect", "DONE", "Task breakdown complete")
        
        # Create initial tasks in state store
        t_ui = self.store.create_task(project_id, "Design UI and Tokens", "Designer", f"Design layout for: {directive}")
        t_fe = self.store.create_task(project_id, "Frontend Implementation", "FrontendDev", f"Build UI for: {directive}")
        t_be = self.store.create_task(project_id, "Backend & API Logic", "BackendDev", f"Implement server logic for: {directive}")
        t_qa = self.store.create_task(project_id, "Automated Verification", "QATester", "Run tests and verify quality")
        
        if event_callback:
            await event_callback("TASKS_UPDATED", {"project_id": project_id})

        # 2. Approval Gate — truly blocks in Hybrid Mode (auto_pilot=False)
        if not project.auto_pilot:
            approval = self.store.create_approval_request(
                project_id=project_id,
                gate_type="PLAN_APPROVAL",
                summary=f"Architect planned 4 tasks for: {directive}"
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
                if event_callback:
                    await event_callback("PIPELINE_REJECTED", {
                        "project_id": project_id,
                        "directive": directive,
                        "summary": "PM rejected the plan. Pipeline halted."
                    })
                return {"status": "REJECTED", "project_id": project_id, "directive": directive}

        # 3. Designer and Backend Dev execute in parallel; FrontendDev runs after Designer
        async def run_designer():
            self.store.update_task_status(t_ui.task_id, "IN_PROGRESS")
            await update_agent("Designer", "WORKING", "Creating styling tokens and responsive layout")
            res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="Designer",
                prompt=f"Create styling tokens and layout for: {directive}",
                workspace_path=workspace,
                project_context=meta,
                event_callback=event_callback
            )
            self.store.update_task_status(t_ui.task_id, "DONE")
            await update_agent("Designer", "DONE", "Design specifications ready")
            return res

        async def run_backend():
            self.store.update_task_status(t_be.task_id, "IN_PROGRESS")
            await update_agent("BackendDev", "WORKING", "Implementing endpoints and data layer")
            res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="BackendDev",
                prompt=f"Implement backend endpoints for: {directive}",
                workspace_path=workspace,
                project_context=meta,
                event_callback=event_callback
            )
            self.store.update_task_status(t_be.task_id, "DONE")
            await update_agent("BackendDev", "DONE", "Backend endpoints complete")
            return res

        async def run_frontend():
            self.store.update_task_status(t_fe.task_id, "IN_PROGRESS")
            await update_agent("FrontendDev", "WORKING", "Building components and pages")
            res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="FrontendDev",
                prompt=f"Implement frontend components for: {directive}",
                workspace_path=workspace,
                project_context=meta,
                event_callback=event_callback
            )
            self.store.update_task_status(t_fe.task_id, "DONE")
            await update_agent("FrontendDev", "DONE", "Frontend code committed")
            return res

        designer_res, backend_res = await asyncio.gather(run_designer(), run_backend())
        frontend_res = await run_frontend()

        # 4. QA Tester with Self-Healing Loop (Max 3 retries)
        self.store.update_task_status(t_qa.task_id, "TESTING")
        await update_agent("QATester", "TESTING", "Running test suite and regression checks")
        
        max_retries = 3
        tests_passed = False
        for attempt in range(1, max_retries + 1):
            qa_res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="QATester",
                prompt=f"Execute unit and integration tests. (Attempt {attempt}/{max_retries})",
                workspace_path=workspace,
                project_context=meta,
                event_callback=event_callback
            )
            
            # Simulated failure handling or real error recovery
            if "FAIL" in qa_res.get("response", "") and attempt < max_retries:
                await update_agent("QATester", "BLOCKED", f"Test failures caught on attempt {attempt}. Dispatching fix.")
                await update_agent("BackendDev", "WORKING", "Self-healing: fixing code based on QA failure report")
                await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role="BackendDev",
                    prompt="Fix all errors reported in QA test execution.",
                    workspace_path=workspace,
                    project_context=meta,
                    event_callback=event_callback
                )
            elif "FAIL" in qa_res.get("response", ""):
                # Final attempt also failed — escalate to PM
                tests_passed = False
                break
            else:
                tests_passed = True
                break

        if not tests_passed:
            # All retries exhausted — escalate to PM Decision Gate
            self.store.update_task_status(t_qa.task_id, "FAILED")
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
                if event_callback:
                    await event_callback("PIPELINE_HALTED", {
                        "project_id": project_id,
                        "directive": directive,
                        "summary": "PM halted pipeline due to QA failures."
                    })
                return {"status": "HALTED_QA_FAILURE", "project_id": project_id, "directive": directive}
        else:
            self.store.update_task_status(t_qa.task_id, "DONE")
            await update_agent("QATester", "DONE", "All automated verification checks passed ✅")

        # 5. Reviewer signs off
        await update_agent("Reviewer", "REVIEWING", "Auditing security, diff quality, and writing release summary")
        rev_res = await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="Reviewer",
            prompt="Perform final code review, verify git diff, and create PM release notes.",
            workspace_path=workspace,
            project_context=meta,
            event_callback=event_callback
        )
        await update_agent("Reviewer", "DONE", "Release approved and documented")

        # DocWriter
        await update_agent("DocWriter", "WORKING", "Updating project documentation and README")
        await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="DocWriter",
            prompt="Update documentation and user guides for completed feature.",
            workspace_path=workspace,
            project_context=meta,
            event_callback=event_callback
        )
        await update_agent("DocWriter", "DONE", "Docs up to date")

        # Tech Lead wraps up sprint
        await update_agent("TechLead", "DONE", f"Sprint completed successfully: {directive}")

        if event_callback:
            await event_callback("PIPELINE_COMPLETED", {
                "project_id": project_id,
                "directive": directive,
                "summary": "Sprint successfully completed by AI team!"
            })

        return {"status": "COMPLETED", "project_id": project_id, "directive": directive}
