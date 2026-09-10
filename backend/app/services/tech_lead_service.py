import time
import os
import shutil
import subprocess
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
        meta = self.store.get_project_metadata(project_id)
        msg_lower = message.lower()

        # 1. Real AI-Powered Response via Google Antigravity CLI (agy)
        agy_path = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
        if os.path.exists(agy_path) and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                workspace = meta.get("path") or ""
                purpose_desc = standup.get("purpose") or meta.get("purpose_summary") or meta.get("summary") or "Software application"
                dirs_preview = ", ".join([d.rstrip('/') for d in meta.get("directory_structure", []) if not d.startswith('.')][:6])
                
                ai_prompt = (
                    f"You are the Project Tech Lead for the project '{standup['project_name']}'.\n"
                    f"Architecture & Codebase context:\n"
                    f"- Stack: {standup['stack_type']}\n"
                    f"- Purpose/Features: {purpose_desc}\n"
                    f"- Core modules: {dirs_preview}\n"
                    f"- Health: {standup['health_status']} ({standup['progress_percent']}% complete)\n"
                    f"- Active work: {standup['active_items']}\n"
                    f"- Next tasks: {standup['next_steps']}\n\n"
                    f"The PM asks: \"{message}\"\n\n"
                    f"Respond as the friendly, knowledgeable, professional Tech Lead in natural, fluent Thai. "
                    f"Explain what the project actually is, what it does, its key systems and technologies, and current status. "
                    f"Be helpful, informative, and avoid stiff template phrasing. (2-3 paragraphs max)"
                )
                res = subprocess.run(
                    [agy_path, "-p", ai_prompt, "--effort", "low"],
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                    cwd=workspace if os.path.exists(workspace) else None
                )
                if res.returncode == 0 and res.stdout.strip():
                    return {
                        "project_id": project_id,
                        "role": "TechLead",
                        "message": res.stdout.strip(),
                        "timestamp": time.time()
                    }
            except Exception:
                pass

        # 2. Project Overview & Purpose Fallback (Thai & English)
        if any(k in msg_lower for k in [

            "about", "purpose", "overview", "what is", "explain", "describe", "summary",
            "เกี่ยวกับอะไร", "คืออะไร", "ทำอะไร", "อธิบาย", "งานนี้", "โปรเจกต์นี้", "สรุปงาน", "ทำอะไรอยู่"
        ]):
            purpose_text = standup.get("purpose") or meta.get("purpose_summary") or meta.get("summary")
            if not purpose_text or purpose_text.strip() == "":
                purpose_text = f"ระบบ {standup['stack_type']} ใน workspace"

            frameworks_str = ", ".join(meta.get("frameworks", [])) if meta.get("frameworks") else ""
            stack_desc = f"{standup['stack_type']}" + (f" ({frameworks_str})" if frameworks_str else "")
            
            # Key directories or files if available
            dirs = [d.rstrip('/') for d in meta.get("directory_structure", []) if not d.startswith('.')][:4]
            dir_hint = f" โครงสร้างสำคัญ: {', '.join(dirs)}" if dirs else ""

            reply = (
                f"โปรเจกต์ '{standup['project_name']}' ({stack_desc}): {purpose_text} ครับ{dir_hint} "
                f"ปัจจุบันสถานะทีมคือ {standup['health_status']} มีความคืบหน้ารวม {standup['progress_percent']}% "
                f"({'มีงาน active: ' + standup['active_items'][0] if standup['active_items'] else 'ทีมพร้อมรับ directive ถัดไป'})"
            )
        # 2. Status & Progress
        elif any(k in msg_lower for k in ["status", "how", "update", "progress", "สถานะ", "คืบหน้า", "เป็นไง", "ถึงไหน", "เช็คสถานะ"]):
            reply = (
                f"Currently our project '{standup['project_name']}' is {standup['health_status']}. "
                f"Progress stands at {standup['progress_percent']}% ({len(standup['completed_items'])} done, "
                f"{len(standup['active_items'])} active). {standup['summary']}"
            )
        # 3. Blockers & Issues
        elif any(k in msg_lower for k in ["block", "stuck", "error", "fail", "ปัญหา", "ติด", "บั๊ก", "พัง"]):
            if standup["blockers"]:
                reply = f"Here are the active blockers: " + "; ".join(standup["blockers"])
            else:
                reply = "Good news! There are zero blockers right now. All agents are executing smoothly."
        # 4. Next Steps & Priorities
        elif any(k in msg_lower for k in ["next", "priority", "todo", "ต่อไป", "ถัดไป", "แพลน", "ทำต่อ"]):
            reply = f"Our top next steps are: " + "; ".join(standup["next_steps"])
        # 5. Technology Stack
        elif any(k in msg_lower for k in ["tech", "stack", "framework", "สแตก", "ภาษา", "เทคโนโลยี", "tool"]):
            reply = f"We are built on {standup['stack_type']}. Project scope: {standup.get('purpose', 'Standard software workspace')}."
        else:
            reply = (
                f"รับทราบครับ! ในฐานะ Tech Lead ของโปรเจกต์ {standup['project_name']} ({standup['stack_type']}) "
                f"บันทึกข้อความ: '{message}' เรียบร้อยแล้วครับ ปัจจุบันสถานะทีมคือ {standup['health_status']} "
                f"ความคืบหน้า {standup['progress_percent']}% หากต้องการดูภาพรวม ถามว่า 'งานนี้เกี่ยวกับอะไร' หรือ 'ขอสถานะ' ได้เลยครับ"
            )

        return {
            "project_id": project_id,
            "role": "TechLead",
            "message": reply,
            "timestamp": time.time()
        }

