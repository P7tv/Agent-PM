import time
from typing import Dict, Any, List
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager

class TechLeadService:
    def __init__(self, store: StateStore, pm: ProjectManager):
        self.store = store
        self.pm = pm

    def generate_standup(self, project_id: str) -> Dict[str, Any]:
        project = self.store.get_project(project_id)
        if not project:
            raise KeyError(f"Project {project_id} not found")

        meta = self.store.get_project_metadata(project_id)
        tasks = self.store.get_tasks(project_id)
        agents = self.store.get_all_agent_states(project_id)

        done_tasks = [t for t in tasks if t.status.value == "DONE"]
        active_tasks = [t for t in tasks if t.status.value in ["IN_PROGRESS", "TESTING", "REVIEW"]]
        todo_tasks = [t for t in tasks if t.status.value == "TODO"]
        failed_tasks = [t for t in tasks if t.status.value == "FAILED"]

        # Health status logic
        blocked_agents = [a for a in agents if a.status.value == "BLOCKED"]
        if blocked_agents or failed_tasks:
            health_status = "BLOCKED"
        elif any(a.status.value == "REVIEWING" for a in agents) and len(active_tasks) > 3:
            health_status = "AT_RISK"
        else:
            health_status = "ON_TRACK"

        progress_pct = int((len(done_tasks) / len(tasks)) * 100) if tasks else (100 if done_tasks else 0)

        completed_items = [f"[{t.assigned_to}] {t.title}" for t in done_tasks]
        active_items = [f"[{t.assigned_to}] {t.title} ({t.status.value})" for t in active_tasks]
        blockers = []
        for ba in blocked_agents:
            blockers.append(f"{ba.role}: {ba.thought or 'Blocked waiting for resolution'}")
        for ft in failed_tasks:
            blockers.append(f"Task Failed: {ft.title} ({ft.description})")

        next_steps = []
        if todo_tasks:
            next_steps.extend([f"[{t.assigned_to}] {t.title}" for t in todo_tasks[:3]])
        elif active_tasks:
            next_steps.append("Complete ongoing tasks and proceed to QA regression validation")
        else:
            next_steps.append("Ready for next PM directive or release deployment")

        proj_name = project.name or meta.get("suggested_name") or "Project"
        stack = meta.get("stack_type", "Generic")
        purpose = meta.get("purpose_summary", "")

        summary = (
            f"Daily Standup for {proj_name} ({stack}): Team is currently {health_status.replace('_', ' ')}. "
            f"{len(done_tasks)}/{len(tasks)} tasks completed ({progress_pct}%). "
        )
        if blockers:
            summary += f"⚠️ {len(blockers)} blocker(s) require attention: {blockers[0]}."
        elif active_tasks:
            summary += f"Active focus: {active_items[0]}."
        else:
            summary += "All systems nominal and waiting for PM instructions."

        return {
            "project_id": project_id,
            "project_name": proj_name,
            "lead_name": "Project Tech Lead",
            "health_status": health_status,
            "progress_percent": progress_pct,
            "summary": summary,
            "purpose": purpose,
            "stack_type": stack,
            "completed_items": completed_items,
            "active_items": active_items,
            "blockers": blockers,
            "next_steps": next_steps,
            "timestamp": time.time()
        }

    def chat_with_lead(self, project_id: str, message: str) -> Dict[str, Any]:
        standup = self.generate_standup(project_id)
        msg_lower = message.lower()

        # Context-aware conversational responses
        if any(k in msg_lower for k in ["status", "how", "update", "progress", "สถานะ", "คืบหน้า"]):
            reply = (
                f"Currently our project '{standup['project_name']}' is {standup['health_status']}. "
                f"Progress stands at {standup['progress_percent']}% ({len(standup['completed_items'])} done, "
                f"{len(standup['active_items'])} active). {standup['summary']}"
            )
        elif any(k in msg_lower for k in ["block", "stuck", "error", "fail", "ปัญหา", "ติด"]):
            if standup["blockers"]:
                reply = f"Here are the active blockers: " + "; ".join(standup["blockers"])
            else:
                reply = "Good news! There are zero blockers right now. All agents are executing smoothly."
        elif any(k in msg_lower for k in ["next", "priority", "todo", "ต่อไป", "ทำอะไร"]):
            reply = f"Our top next steps are: " + "; ".join(standup["next_steps"])
        elif any(k in msg_lower for k in ["tech", "stack", "framework", "สแตก"]):
            reply = f"We are built on {standup['stack_type']}. Project scope: {standup.get('purpose', 'Standard web service')}."
        else:
            reply = (
                f"Understood! As Tech Lead for {standup['project_name']}, I've noted that: '{message}'. "
                f"Current team progress is {standup['progress_percent']}% with health status {standup['health_status']}."
            )

        return {
            "project_id": project_id,
            "role": "TechLead",
            "message": reply,
            "timestamp": time.time()
        }
