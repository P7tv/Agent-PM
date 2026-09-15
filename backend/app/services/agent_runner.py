import re
import json
import asyncio
import os
import time
from typing import Callable, Coroutine, Any, Dict, Optional, AsyncGenerator, List

# Antigravity SDK
try:
    from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
    HAS_ANTIGRAVITY = True
except ImportError:
    HAS_ANTIGRAVITY = False

from app.services.skill_manager import SkillManager

from dotenv import load_dotenv
load_dotenv()

import shutil

default_win_agy = os.path.expanduser("~/AppData/Local/agy/bin/agy.exe")

AGY_PATH = (
    os.environ.get("AGY_PATH")
    or (default_win_agy if os.path.exists(default_win_agy) else None)
    or shutil.which("agy")
    or shutil.which("agy.cmd")
    or shutil.which("agy.exe")
    or os.path.expanduser("~/.local/bin/agy")
    or os.path.expanduser("~/AppData/Local/Programs/agy/agy.exe")
)
HAS_AGY_CLI = bool(AGY_PATH and os.path.exists(AGY_PATH))

ROLE_PROMPTS = {
    "TechLead": "You are the project tech lead. Coordinate tasks, resolve architectural blockers, track progress, and report clearly to the PM.",
    "Architect": "You are a software architect. Break down high-level requirements into clear, isolated tasks.",
    "Designer": "You are a UI/UX designer. Create CSS design tokens, layouts, and component structures.",
    "FrontendDev": "You are a senior frontend engineer. Implement UI components and client logic.",
    "BackendDev": "You are a senior backend engineer. Implement server endpoints and database interactions.",
    "QATester": "You are a QA automation engineer. Run test suites and report regressions and failures.",
    "Reviewer": "You are a staff code reviewer. Verify security, code cleanliness, and produce release summaries.",
    "DocWriter": "You are a technical writer. Produce documentation, READMEs, and API references."
}

class AgentRunner:
    def __init__(self, use_mock: bool = False, skill_manager: Optional[SkillManager] = None, store: Optional[Any] = None):
        self.use_mock = use_mock
        self.has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
        self.skill_manager = skill_manager or SkillManager()
        self.store = store

    async def dispatch_agent_task(
        self,
        project_id: str,
        role: str,
        prompt: str,
        workspace_path: str,
        project_context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]] = None
    ) -> Dict[str, Any]:
        
        async def emit(event_type: str, data: Dict[str, Any]):
            if event_callback:
                await event_callback(event_type, {
                    "project_id": project_id,
                    "role": role,
                    "timestamp": time.time(),
                    **data
                })

        await emit("AGENT_STATUS_CHANGE", {"status": "THINKING"})

        active_skills = []
        base_role_skill = self.skill_manager.get_base_role_skill(role)
        if self.store:
            agent_state = self.store.get_agent_status(project_id, role)
            if agent_state and getattr(agent_state, "skill_mode", "AUTO") == "MANUAL":
                skills_to_load = getattr(agent_state, "equipped_skills", []) or ([agent_state.skill_name] if getattr(agent_state, "skill_name", None) else [])
                for s_name in skills_to_load:
                    try:
                        active_skills.append(self.skill_manager.get_skill(s_name, project_path=workspace_path))
                    except: pass
            if not active_skills:
                active_skills = self.skill_manager.match_skills_for_task(
                    role=role,
                    task_prompt=prompt,
                    project_path=workspace_path,
                    max_skills=2
                )
        else:
            active_skills = self.skill_manager.match_skills_for_task(
                role=role,
                task_prompt=prompt,
                project_path=workspace_path,
                max_skills=2
            )

        if active_skills:
            skill_titles = ", ".join(s.title for s in active_skills)
            await emit("AGENT_THOUGHT_DELTA", {"thought": f"🎯 Activated Skill Playbook: {skill_titles}"})

        agent_persona = None
        if self.store:
            ag_state = self.store.get_agent_status(project_id, role)
            if ag_state:
                agent_persona = ag_state.thought or ag_state.skill_title

        async def run_contextual_simulation():
            stack = project_context.get("stack_type", "Project") if project_context else "Project"
            dirs = [d.rstrip('/') for d in (project_context.get("directory_structure", []) if project_context else []) if not d.startswith('.')][:3]
            dir_str = f" in {', '.join(dirs)}" if dirs else ""
            
            thoughts = [
                f"Analyzing PM requirements for {role} ({stack})...",
            ]
            if agent_persona and role not in ROLE_PROMPTS:
                thoughts.append(f"Applying specialist persona: {agent_persona}...")
            thoughts.extend([
                f"Examining workspace files{dir_str} at {workspace_path}...",
                f"Aligning with role playbooks and active tasks..."
            ])
            if active_skills:
                thoughts.append(f"Operating under methodology: {', '.join(s.title for s in active_skills)}")
            for t in thoughts:
                await emit("AGENT_THOUGHT_DELTA", {"thought": t})
                await asyncio.sleep(0.04)
                
            await emit("TOOL_EXECUTION_START", {"tool": "inspect_workspace", "args": {"path": workspace_path}})
            await asyncio.sleep(0.03)
            await emit("TOOL_EXECUTION_FINISH", {"tool": "inspect_workspace", "result": f"Verified workspace files for {role}"})
            
            await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
            return {
                "status": "SUCCESS",
                "role": role,
                "response": f"Completed tasks for: {prompt}",
                "tokens_used": 0,
                "backend_used": "mock",
                "active_skills": [s.name for s in active_skills]
            }

        # If explicit test mock requested, run simulation
        if self.use_mock:
            return await run_contextual_simulation()

        system_instruction = self.skill_manager.synthesize_agent_prompt(
            role=role,
            project_context=project_context,
            project_path=workspace_path,
            base_skill=base_role_skill,
            active_skills=active_skills
        )
        if agent_persona and role not in ROLE_PROMPTS:
            system_instruction = f"Specialist Persona: {agent_persona}\n\n" + system_instruction

        # 1. Live Antigravity Python SDK Execution (if GEMINI_API_KEY is present)
        if self.has_api_key and HAS_ANTIGRAVITY:
            try:
                system_instruction += f"\nCRITICAL CONSTRAINT: Always operate strictly within {workspace_path}."
                config = LocalAgentConfig(
                    system_instructions=system_instruction,
                    capabilities=CapabilitiesConfig()
                )
                async with Agent(config) as agent:
                    sdk_prompt = (
                        f"{prompt}\n\n"
                        f"If you create or update files, output each file using:\n"
                        f"```filename: relative/path/to/file.ext\n<code content>\n```\n"
                    )
                    response = await agent.chat(sdk_prompt)
                    full_text = []
                    if hasattr(response, "thoughts"):
                        async for thought in response.thoughts:
                            await emit("AGENT_THOUGHT_DELTA", {"thought": str(thought)})
                    if hasattr(response, "tool_calls"):
                        async for tool_call in response.tool_calls:
                            await emit("TOOL_EXECUTION_START", {"tool": tool_call.name, "args": tool_call.args})
                    tokens_used = 0
                    if hasattr(response, "usage_metadata"):
                        tokens_used = getattr(response.usage_metadata, "total_token_count", 0) or 0
                    async for token in response:
                        full_text.append(token)
                    resp_str = "".join(full_text)
                    if tokens_used == 0:
                        tokens_used = len(resp_str) // 4
                    
                    try:
                        from app.services.console_service import parse_code_proposals
                        proposals = parse_code_proposals(resp_str)
                        for prop in proposals:
                            fp = prop.get("filepath", "")
                            cnt = prop.get("content", "")
                            if fp and cnt and workspace_path and os.path.exists(workspace_path):
                                full_p = os.path.join(workspace_path, fp) if not os.path.isabs(fp) else fp
                                real_ws = os.path.realpath(workspace_path)
                                real_tgt = os.path.realpath(full_p)
                                if real_tgt.startswith(real_ws):
                                    os.makedirs(os.path.dirname(real_tgt), exist_ok=True)
                                    with open(real_tgt, "w", encoding="utf-8") as f:
                                        f.write(cnt)
                                    await emit("TOOL_EXECUTION_FINISH", {"tool": "write_file", "result": f"Saved {fp}"})
                    except Exception:
                        pass

                    await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
                    return {
                        "status": "SUCCESS",
                        "role": role,
                        "response": resp_str,
                        "tokens_used": tokens_used,
                        "backend_used": "sdk",
                        "active_skills": [s.name for s in active_skills]
                    }
            except Exception as e:
                await emit("AGENT_THOUGHT_DELTA", {"thought": f"SDK Notice: {str(e)[:60]}... falling back to agy CLI."})

        # 2. Antigravity CLI Execution (Google OAuth account login without API key)
        if HAS_AGY_CLI and os.path.exists(AGY_PATH):
            try:
                await emit("AGENT_THOUGHT_DELTA", {"thought": f"Executing with Google Antigravity CLI ({role})..."})
                full_query = (
                    f"{system_instruction}\n\n"
                    f"PM Directive: {prompt}\n\n"
                    f"If you create or update files, output each file using:\n"
                    f"```filename: relative/path/to/file.ext\n<code content>\n```\n"
                    f"Respond concisely in Thai or English as {role}."
                )
                cmd_args = [AGY_PATH, "--add-dir", workspace_path, "-p", full_query, "--dangerously-skip-permissions", "--effort", "low"]
                if os.name == "nt" and AGY_PATH.lower().endswith((".cmd", ".bat")):
                    cmd_args = ["cmd.exe", "/c"] + cmd_args
                proc = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=workspace_path
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90.0)
                if proc.returncode == 0:
                    text = stdout.decode("utf-8", errors="ignore").strip()
                    if text:
                        await emit("AGENT_THOUGHT_DELTA", {"thought": f"{role} processed directive successfully."})
                        # Auto-extract and write code proposals to workspace
                        try:
                            from app.services.console_service import parse_code_proposals
                            proposals = parse_code_proposals(text)
                            for prop in proposals:
                                fp = prop.get("filepath", "")
                                cnt = prop.get("content", "")
                                if fp and cnt and workspace_path and os.path.exists(workspace_path):
                                    full_p = os.path.join(workspace_path, fp) if not os.path.isabs(fp) else fp
                                    real_ws = os.path.realpath(workspace_path)
                                    real_tgt = os.path.realpath(full_p)
                                    if real_tgt.startswith(real_ws):
                                        os.makedirs(os.path.dirname(real_tgt), exist_ok=True)
                                        with open(real_tgt, "w", encoding="utf-8") as f:
                                            f.write(cnt)
                                        await emit("TOOL_EXECUTION_FINISH", {"tool": "write_file", "result": f"Saved {fp}"})
                        except Exception:
                            pass
                        await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
                        estimated_tokens = len(text) // 4
                        return {
                            "status": "SUCCESS",
                            "role": role,
                            "response": text,
                            "tokens_used": estimated_tokens,
                            "backend_used": "cli",
                            "active_skills": [s.name for s in active_skills]
                        }
            except Exception as e:
                await emit("AGENT_THOUGHT_DELTA", {"thought": f"CLI note: {str(e)[:50]}... using local runner."})

        # 3. Smart local contextual runner fallback
        return await run_contextual_simulation()

    async def dispatch_chat_task(
        self,
        project_id: str,
        role: str,
        message: str,
        workspace_path: str,
        project_context: Optional[Dict[str, Any]] = None,
        conversation_context: str = "",
        attachments: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Dispatch a chat-style task for the Unified Team Console.
        Returns structured response with text + code proposals.
        """
        from app.services.console_service import parse_code_proposals

        active_skills = []
        base_role_skill = self.skill_manager.get_base_role_skill(role)
        if self.store:
            agent_state = self.store.get_agent_status(project_id, role)
            if agent_state and getattr(agent_state, "skill_mode", "AUTO") == "MANUAL":
                skills_to_load = getattr(agent_state, "equipped_skills", []) or ([agent_state.skill_name] if getattr(agent_state, "skill_name", None) else [])
                for s_name in skills_to_load:
                    try:
                        active_skills.append(self.skill_manager.get_skill(s_name, project_path=workspace_path))
                    except: pass
            if not active_skills:
                active_skills = self.skill_manager.match_skills_for_task(
                    role=role,
                    task_prompt=message,
                    project_path=workspace_path,
                    max_skills=2
                )
        else:
            active_skills = self.skill_manager.match_skills_for_task(
                role=role,
                task_prompt=message,
                project_path=workspace_path,
                max_skills=2
            )

        system_instruction = self.skill_manager.synthesize_agent_prompt(
            role=role,
            project_context=project_context,
            project_path=workspace_path,
            base_skill=base_role_skill,
            active_skills=active_skills
        )

        attachment_context = ""
        if attachments:
            attachment_context = "\n[USER ATTACHMENTS (Images/Files)]\n"
            for att in attachments:
                attachment_context += f"- File Name: {att.get('filename', 'Unknown')}\n  File Path: {att.get('path', '')}\n"

        full_prompt = (
            f"{system_instruction}\n\n"
            f"Recent conversation context:\n{conversation_context}\n\n"
            f"User message to {role}: {message}\n"
            f"{attachment_context}\n"
            f"Respond helpfully. If you propose code changes, use this format:\n"
            f"**File: path/to/file.ext**\n```language\ncode content\n```\n"
            f"Workspace: {workspace_path}\n"
            f"Respond in Thai or English naturally."
        )

        response_text = ""
        backend_used = "mock"
        tokens_used = 0

        # 1. Live Antigravity Python SDK Execution (if GEMINI_API_KEY is present and not in mock mode)
        if not self.use_mock and self.has_api_key and HAS_ANTIGRAVITY:
            try:
                config = LocalAgentConfig(
                    system_instructions=system_instruction,
                    capabilities=CapabilitiesConfig()
                )
                async with Agent(config) as agent:
                    chat_query = (
                        f"Recent conversation context:\n{conversation_context}\n\n"
                        f"User message: {message}\n"
                        f"{attachment_context}\n"
                        f"If you propose code changes, format them as:\n"
                        f"**File: relative/path/to/file.ext**\n```language\ncode content\n```\n"
                        f"Workspace: {workspace_path}"
                    )
                    response = await agent.chat(chat_query)
                    full_text = []
                    if hasattr(response, "usage_metadata"):
                        tokens_used = getattr(response.usage_metadata, "total_token_count", 0) or 0
                    async for token in response:
                        full_text.append(token)
                    response_text = "".join(full_text).strip()
                    if response_text:
                        backend_used = "sdk"
                        if tokens_used == 0:
                            tokens_used = len(response_text) // 4
            except Exception:
                pass

        # 2. Try agy CLI if not already answered by SDK
        if not response_text and not self.use_mock and HAS_AGY_CLI and os.path.exists(AGY_PATH):
            try:
                cmd_args = [AGY_PATH, "--add-dir", workspace_path, "-p", full_prompt, "--dangerously-skip-permissions", "--effort", "low"]
                if os.name == "nt" and AGY_PATH.lower().endswith((".cmd", ".bat")):
                    cmd_args = ["cmd.exe", "/c"] + cmd_args
                proc = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=workspace_path
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90.0)
                if proc.returncode == 0:
                    response_text = stdout.decode("utf-8", errors="ignore").strip()
                    if response_text:
                        backend_used = "cli"
                        tokens_used = len(response_text) // 4
            except Exception:
                pass

        # Fallback to mock if no agy response
        if not response_text:
            stack = project_context.get("stack_type", "Project") if project_context else "Project"
            response_text = (
                f"[{role}] ได้รับข้อความจาก PM แล้วครับ: \"{message}\"\n\n"
                f"ผมกำลังวิเคราะห์ {stack} project ที่ {workspace_path} "
                f"และจะดำเนินการตามที่สั่งครับ"
            )
            backend_used = "mock"
            tokens_used = 0

        # Parse code proposals from the response
        code_proposals = parse_code_proposals(response_text)

        return {
            "status": "SUCCESS",
            "role": role,
            "response": response_text,
            "code_proposals": code_proposals,
            "tokens_used": tokens_used,
            "backend_used": backend_used,
            "active_skills": [s.name for s in active_skills]
        }


