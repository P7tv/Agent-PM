import re
import json
import asyncio
import os
import time
from pathlib import Path
from app.services.process_runner import run_process
from app.services.runtime_adapter import AntigravityAdapter
from app.services.context_assembler import assemble_task_context
from typing import Callable, Coroutine, Any, Dict, Optional, AsyncGenerator, List

# Antigravity SDK
try:
    from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
    HAS_ANTIGRAVITY = True
except ImportError:
    HAS_ANTIGRAVITY = False

from app.services.skill_manager import SkillManager
from app.services.prompt_builder import build_prompt, mode_for_role, READ_ONLY_MODES, handoff_text

from dotenv import load_dotenv
load_dotenv()

import shutil

default_win_agy = os.path.expanduser("~/AppData/Local/agy/bin/agy.exe")

_agy_candidates = [default_win_agy, shutil.which('agy'), shutil.which('agy.cmd'), shutil.which('agy.exe'),
                   os.path.expanduser('~/.local/bin/agy'), os.path.expanduser('~/AppData/Local/Programs/agy/agy.exe')]
AGY_PATH = os.environ.get('AGY_PATH') or next((path for path in _agy_candidates if path and os.path.isfile(path)), None)

HAS_AGY_CLI = bool(AGY_PATH and os.path.exists(AGY_PATH))

class CLIExecutionError(RuntimeError):
    def __init__(self, message, code="CLI_ERROR"):
        super().__init__(message)
        self.code = code


class CLIResponse(str):
    def __new__(cls, text, tokens_used=0):
        value = super().__new__(cls, text)
        value.tokens_used = tokens_used
        return value


def parse_cli_response(result):
    """Inspect the print-mode result even when the CLI exits successfully."""
    raw = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()
    payload = None
    try:
        payload = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        pass
    if isinstance(payload, dict):
        status = str(payload.get("status", "")).upper()
        response = payload.get("response", "")
        detail = payload.get("error") or payload.get("message") or ""
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        failed = status not in {"SUCCESS", "COMPLETED"} or bool(payload.get("is_error"))
        diagnostics = f"{status} {detail} {stderr}".lower()
    else:
        response = raw
        failed = result.get("exit_code") != 0
        diagnostics = f"{raw} {stderr}".lower()
    if failed or result.get("exit_code") != 0 or not isinstance(response, str) or not response.strip():
        if any(term in diagnostics for term in ("not logged", "unauthenticated", "login expired", "authentication", "sign in")):
            raise CLIExecutionError("CLI ยังไม่ได้เข้าสู่ระบบหรือ session หมดอายุ กรุณาเข้าสู่ระบบ agy แล้วลองใหม่", "AUTH_REQUIRED")
        if any(term in diagnostics for term in ("permission", "confirmation", "approval", "soft-den", "denied")):
            raise CLIExecutionError("CLI หยุดรอสิทธิ์ใช้เครื่องมือในโหมด non-interactive", "PERMISSION_REQUIRED")
        if any(term in diagnostics for term in ("quota", "resource_exhausted", "rate limit")):
            raise CLIExecutionError("CLI ถูกจำกัด quota หรือ rate limit กรุณาลองใหม่ภายหลัง", "RATE_LIMITED")
        if isinstance(response, str) and not response.strip() and not failed and result.get("exit_code") == 0:
            raise CLIExecutionError(
                "CLI จบโดยไม่มีคำตอบสุดท้าย อาจหยุดที่การขอสิทธิ์ใช้เครื่องมือ; ยังไม่ถือว่างานสำเร็จ",
                "EMPTY_RESPONSE",
            )
        detail = (payload.get("error") or payload.get("message") or stderr or payload.get("status")) if isinstance(payload, dict) else stderr or raw
        raise CLIExecutionError(f"CLI execution failed: {str(detail)[:1200]}", "CLI_ERROR")
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
    return CLIResponse(response.strip(), tokens if isinstance(tokens, int) else 0)

class AgentRunner:
    def __init__(self, use_mock: bool = False, skill_manager: Optional[SkillManager] = None, store: Optional[Any] = None):
        self.use_mock = use_mock
        self.has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
        self.skill_manager = skill_manager or SkillManager()
        self.store = store
        self.last_runtime_error = None

    def prepare_prompt(self, project_id, role, workspace_path, prompt="", project_context=None, mode=None):
        agent = self.store.get_agent_status(project_id, role) if self.store else None
        bundle = build_prompt(self.skill_manager, role, workspace_path, project_context, agent, prompt, mode)
        bundle.trace["task_characters"] = len(prompt)
        if len(bundle.system) + len(prompt) + 1000 > bundle.trace["max_characters"]:
            raise ValueError("Prompt and required task exceed the context budget; shorten the task or split the directive")
        return bundle

    def selected_backend(self):
        preference = os.environ.get('AGENT_RUNTIME', 'auto')
        cli = bool(HAS_AGY_CLI and os.path.isfile(AGY_PATH))
        sdk = self.has_api_key and HAS_ANTIGRAVITY
        if self.use_mock: return 'mock'
        if preference not in {'auto', 'cli', 'sdk'}: return 'unavailable'
        if cli and preference != 'sdk': return 'cli'
        if sdk and preference != 'cli': return 'sdk'
        return 'unavailable'

    def runtime_status(self):
        sdk = self.selected_backend() == 'sdk'
        cli = self.selected_backend() == 'cli'
        status = {
            "available": bool(sdk or cli or self.use_mock),
            "capabilities": {"streaming": cli, "exact_session_resume": cli, "pause": True,
                             "live_instruction_injection": False, "terminal_sandbox_requested": cli,
                             "skill_tool_allowlist_enforced": False},
            "requested_model": os.environ.get("AGENT_MODEL") or None,
            "cli_file_mode": os.environ.get('AGENT_CLI_FILE_MODE', 'host-proposals'),
            "mode": "mock" if self.use_mock else "sdk" if sdk else "cli" if cli else "unavailable",
            "message": "โหมดจำลอง: ไม่มีการสร้างไฟล์จริง" if self.use_mock else
                       "พร้อมเรียก AI (จะตรวจการเชื่อมต่อเมื่อเริ่มงาน)" if sdk or cli else
                       "ไม่พบ AI runtime: ตั้งค่า AGY_PATH และเข้าสู่ระบบ agy หรือใช้ SDK พร้อม GEMINI_API_KEY",
        }
        if self.last_runtime_error and not self.use_mock:
            status["last_error"] = self.last_runtime_error
            status["message"] = f"พบ {status['mode']} runtime แต่การเรียกครั้งล่าสุดไม่สำเร็จ: {self.last_runtime_error['message']}"
        return status

    async def _run_cli(self, prompt, workspace_path, emit=None, chat=False, conversation_id=None):
        timeout = max(1.0, float(os.environ.get("AGENT_TIMEOUT_SECONDS", "600")))
        model = os.environ.get('AGENT_MODEL', '').strip()
        model_effort = re.search(r'-(low|medium|high)$', model)
        effort = os.environ.get("AGENT_EFFORT") or (model_effort.group(1) if model_effort else 'high')
        if effort not in {"low", "medium", "high"}:
            raise ValueError("AGENT_EFFORT must be low, medium, or high")
        if model_effort and model_effort.group(1) != effort:
            raise ValueError(f'AGENT_EFFORT={effort} conflicts with AGENT_MODEL={model}; choose a matching effort or unset AGENT_EFFORT')
        started = time.monotonic()
        if chat:
            prompt += (
                "\nRead-only planning: use file browsing/read tools only. Do not invoke terminal, RunCommand, "
                "or tools requiring confirmation. If repository inspection is unavailable, return your analysis "
                "from the supplied context and explicitly list unverified assumptions. If source context is supplied, "
                "use it without calling any tools. Always finish with a final text response."
            )
        else:
            prompt += (
                "\nNon-interactive implementation: browse/read files and use direct file editing tools "
                "(replace_file_content, multi_replace_file_content, write_to_file). Do not use RunCommand, "
                "terminal, shell scripts, package installation, or web tools. The host runs configured "
                "checks after your edits and returns their measured results for repairs. Do not create "
                "or execute a helper script to write files. If direct file tools are unavailable, report "
                "that blocker explicitly. Finish with changed paths and unrun checks."
            )
        async def progress(elapsed):
            if emit:
                await emit("AGENT_PROGRESS", {
                    "message": f"กำลังรอผลจาก AI • {int(elapsed)} วินาที (สูงสุด {int(timeout)} วินาที)",
                    "elapsed_seconds": elapsed,
                })
        for attempt in range(2 if chat else 1):
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError(f"Execution timed out after {timeout:g} seconds")
            adapter = AntigravityAdapter(AGY_PATH, executor=run_process)
            result, stream = await adapter.start_task(
                prompt, workspace_path, remaining, effort, readonly=chat, emit=emit,
                progress=progress, conversation_id=conversation_id,
                model=model or None)
            try:
                response = parse_cli_response(result)
                response.conversation_id = stream.conversation_id
                response.reported_model = stream.model
                return response
            except CLIExecutionError as exc:
                exc.conversation_id = stream.conversation_id
                exc.reported_model = stream.model
                try:
                    usage = json.loads(result.get('stdout', '{}')).get('usage', {})
                    counted = usage.get('total_tokens', 0) if isinstance(usage, dict) else 0
                except (ValueError, AttributeError):
                    counted = 0
                exc.tokens_used = counted if isinstance(counted, int) and counted >= 0 else 0
                exc.usage_source = 'provider' if exc.tokens_used else 'unavailable'
                if exc.code == 'PERMISSION_REQUIRED' and stream.failed_tool:
                    exc.args = (f'{exc} • เครื่องมือ: {stream.failed_tool}; ไฟล์พักงานยังเก็บไว้',)
                if not chat or attempt or exc.code not in {"EMPTY_RESPONSE", "PERMISSION_REQUIRED"}:
                    raise
                if emit:
                    await emit("AGENT_PROGRESS", {"message": "CLI ไม่ส่งคำตอบหรือรอสิทธิ์ กำลังลองวิเคราะห์อีกครั้งโดยไม่ใช้เครื่องมือ (1/1)"})
                prompt += "\nRecovery: return the final requested analysis directly now. Do not call any tools."

    async def _write_proposals(self, text, workspace_path, emit):
        from app.services.console_service import parse_code_proposals
        root = Path(workspace_path).resolve()
        proposals = parse_code_proposals(text)
        targets = []
        # Validate the complete batch before writing any file.
        for proposal in proposals:
            relative = Path(proposal["filepath"])
            target = (root / relative).resolve()
            if relative.is_absolute() or root not in target.parents or ".git" in target.relative_to(root).parts:
                raise ValueError(f"Unsafe output path: {relative}")
            targets.append((target, proposal))
        for target, proposal in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(proposal["content"], encoding="utf-8")
            await emit("TOOL_EXECUTION_FINISH", {"tool": "write_file", "result": f"Saved {proposal['filepath']}"})

    async def dispatch_agent_task(
        self,
        project_id: str,
        role: str,
        prompt: str,
        workspace_path: str,
        project_context: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        conversation_id: Optional[str] = None
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

        try:
            prompt, project_context = assemble_task_context(prompt, project_context)
            bundle = self.prepare_prompt(project_id, role, workspace_path, prompt, project_context)
        except (ValueError, OSError) as error:
            await emit("AGENT_STATUS_CHANGE", {"status": "BLOCKED", "thought": str(error)})
            return {"status": "FAILED", "role": role, "error": str(error), "response": str(error),
                    "error_code": "PROMPT_INVALID", "tokens_used": 0, "backend_used": "unavailable", "active_skills": []}
        active_skills = bundle.active_skills
        await emit("AGENT_PROMPT_READY", {"trace": bundle.trace})
        if self.store:
            self.store.save_prompt_trace(project_id, role, bundle.trace)
        if bundle.trace["warnings"]:
            await emit("AGENT_PROGRESS", {"message": "Prompt warnings: " + "; ".join(bundle.trace["warnings"])})

        if active_skills:
            skill_titles = ", ".join(s.title for s in active_skills)
            await emit("AGENT_THOUGHT_DELTA", {"thought": f"🎯 Activated Skill Playbook: {skill_titles}"})

        agent_state = self.store.get_agent_status(project_id, role) if self.store else None
        agent_persona = agent_state.persona if agent_state else None

        async def run_contextual_simulation():
            stack = project_context.get("stack_type", "Project") if project_context else "Project"
            dirs = [d.rstrip('/') for d in (project_context.get("directory_structure", []) if project_context else []) if not d.startswith('.')][:3]
            dir_str = f" in {', '.join(dirs)}" if dirs else ""
            
            thoughts = [
                f"Analyzing PM requirements for {role} ({stack})...",
            ]
            if agent_persona:
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
                "active_skills": [s.name for s in active_skills], "prompt_trace": bundle.trace,
            }

        # If explicit test mock requested, run simulation
        if self.use_mock:
            return await run_contextual_simulation()

        system_instruction = bundle.system
        # Planning, design, QA, and review must not mutate the checkout. This
        # keeps verification independent from implementation and prevents an
        # evaluator from silently changing the code it is evaluating.
        planning_only = mode_for_role(role) in READ_ONLY_MODES

        errors = []
        error_code = None
        failed_session = None
        failed_model = None
        failed_tokens = 0
        failed_usage_source = 'unavailable'
        # 1. Live Antigravity Python SDK Execution (if GEMINI_API_KEY is present)
        if self.selected_backend() == 'sdk' and not conversation_id:
            try:
                config = LocalAgentConfig(
                    system_instructions=system_instruction,
                    capabilities=CapabilitiesConfig()
                )
                async with Agent(config) as agent:
                    sdk_prompt = prompt if planning_only else (
                        f"{prompt}\n\n"
                        f"If you create or update files, output each file using:\n"
                        f"```filename: relative/path/to/file.ext\n<code content>\n```\n"
                    )
                    response = await agent.chat(sdk_prompt)
                    full_text = []
                    if hasattr(response, "thoughts"):
                        async for thought in response.thoughts:
                            await emit("AGENT_PROGRESS", {"message": "AI กำลังวิเคราะห์งาน"})
                    if hasattr(response, "tool_calls"):
                        async for tool_call in response.tool_calls:
                            await emit("TOOL_EXECUTION_START", {"tool": tool_call.name})
                    tokens_used = 0
                    if hasattr(response, "usage_metadata"):
                        tokens_used = getattr(response.usage_metadata, "total_token_count", 0) or 0
                    async for token in response:
                        full_text.append(token)
                    resp_str = "".join(full_text)
                    usage_source = 'provider' if tokens_used else 'estimated'
                    if tokens_used == 0:
                        tokens_used = len(resp_str) // 4
                    
                    if not resp_str.strip():
                        raise RuntimeError("AI returned an empty response")
                    if not planning_only:
                        await self._write_proposals(resp_str, workspace_path, emit)

                    await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
                    return {
                        "status": "SUCCESS",
                        "role": role,
                        "response": resp_str,
                        "tokens_used": tokens_used,
                        "backend_used": "sdk", "usage_source": usage_source,
                        "active_skills": [s.name for s in active_skills], "prompt_trace": bundle.trace,
                    }
            except Exception as e:
                # An SDK may already have edited files. Never replay the task on another backend.
                errors.append(f"SDK: {e}")

        # Select the writer before invocation. Never replay failed direct edits.
        if not errors and (self.selected_backend() == 'cli' or conversation_id) and HAS_AGY_CLI and os.path.exists(AGY_PATH):
            try:
                file_mode = os.environ.get('AGENT_CLI_FILE_MODE', 'host-proposals')
                if file_mode not in {'direct', 'host-proposals'}:
                    raise ValueError('AGENT_CLI_FILE_MODE must be direct or host-proposals')
                host_writer = not planning_only and file_mode == 'host-proposals'
                await emit("AGENT_PROGRESS", {"message": f"เริ่มทำงานด้วย Antigravity CLI: {role}"})
                full_query = (
                    f"{system_instruction}\n\nPM Directive: {prompt}\n\n" +
                    ("Inspect and report only; the orchestrator runs deterministic checks. " if planning_only else
                     "Inspect the existing files before making changes. Implement using workspace tools. ") +
                    "Preserve existing behavior and conventions. Do not return replacement file dumps. "
                    "Only perform work required by this directive; if your specialty is not needed, "
                    "explain that briefly instead of creating unrelated features or services. "
                    "Report: completed work, changed file paths, checks actually run with results, "
                    "remaining issues, and the handoff for the next agent. Never claim unrun tests passed. "
                    "For planning roles, specify acceptance criteria, API contracts, and file ownership. "
                    f"Operate only inside {workspace_path}. Respond in the user's language."
                )
                cli_options = {'chat': planning_only}
                if planning_only and file_mode == 'host-proposals':
                    from app.services.workspace_session import snapshot_workspace
                    from app.services.host_file_writer import proposal_context
                    source_context, _ = proposal_context(workspace_path, snapshot_workspace(workspace_path), prompt)
                    full_query += '\nSource context supplied by host (do not call tools): ' + source_context
                if host_writer:
                    from app.services.workspace_session import snapshot_workspace
                    from app.services.host_file_writer import proposal_context
                    baseline = snapshot_workspace(workspace_path)
                    file_context, observed_paths = proposal_context(workspace_path, baseline, prompt)
                    full_query = (f'{system_instruction}\nPM Directive: {prompt}\n'
                        f'Workspace: {workspace_path}. Existing source is supplied below. Do not call any tools. '
                        'This invocation prepares proposals for the host writer. Do not edit files or use terminal tools. '
                        'Return only a JSON object {"files":[{"path":"relative/path","content":"complete file content"}],'
                        '"summary":"changes and unrun checks"}. Include every changed file in full, no markdown fences. '
                        'When contracts or next-owner details are needed, include an optional handoff object '
                        'inside that JSON with summary, changed_files, contracts, checks, risks and next_owner; '
                        'never append agent_handoff tags or prose outside JSON. '
                        'Preserve unrelated existing content. Replace only existing files supplied in full; '
                        'if needed files are omitted, report that blocker. Write the summary in the user\'s language. '
                        'The host validates paths, writes files, then runs checks. '
                        '\nSource context: ' + file_context)
                    if len(full_query) > max(12000, min(200000, int(os.environ.get('AGENT_PROMPT_MAX_CHARS', '48000')))):
                        raise ValueError('Host proposal prompt exceeds the context budget; narrow the task')
                    cli_options['chat'] = True
                if len(full_query) > max(12000, min(200000, int(os.environ.get('AGENT_PROMPT_MAX_CHARS', '48000')))):
                    raise ValueError('CLI prompt exceeds the context budget; narrow the task')
                if conversation_id:
                    cli_options['conversation_id'] = conversation_id
                async def visible_runtime(event, data):
                    if host_writer and event == 'RUNTIME_STEP' and data.get('step_type') == 'agent_response':
                        data = {**data, 'message': 'AI กำลังเตรียมการแก้ไฟล์ให้ backend ตรวจและเขียน'}
                    await emit(event, data)
                text = await self._run_cli(full_query, workspace_path, visible_runtime, **cli_options)
                displayed_text = str(text)
                if host_writer:
                    from app.services.host_file_writer import apply_file_proposals
                    try:
                        payload = json.loads(str(text))
                        normalized_handoff = None
                        if isinstance(payload, dict) and 'handoff' in payload:
                            candidate = '<agent_handoff>' + json.dumps(payload['handoff'], ensure_ascii=False) + '</agent_handoff>'
                            normalized_handoff = json.loads(handoff_text({'response': candidate}))
                            # Host paths below supersede model-reported paths.
                        paths = apply_file_proposals(str(text), workspace_path, baseline, observed_paths)
                    except ValueError as error:
                        failure = CLIExecutionError(f'ข้อเสนอไฟล์จาก AI ไม่ผ่านการตรวจ: {error}; ยังไม่ส่งมอบงาน', 'HOST_PROPOSAL_INVALID')
                        failure.conversation_id = getattr(text, 'conversation_id', None)
                        failure.reported_model = getattr(text, 'reported_model', None)
                        failure.tokens_used = getattr(text, 'tokens_used', 0) or len(text) // 4
                        failure.usage_source = 'provider' if getattr(text, 'tokens_used', 0) else 'estimated'
                        raise failure from error
                    for path in paths:
                        await emit('TOOL_EXECUTION_FINISH', {'tool': 'host_write_file', 'result': f'Saved {path}'})
                    displayed_text = str(json.loads(str(text)).get('summary', 'Host applied file proposals'))[:4000] + '\nFiles: ' + ', '.join(paths)
                    if normalized_handoff is not None:
                        normalized_handoff['changed_files'] = paths
                        normalized_handoff['verified_changed_files'] = paths
                        displayed_text += '\n<agent_handoff>' + json.dumps(normalized_handoff, ensure_ascii=False) + '</agent_handoff>'
                self.last_runtime_error = None
                await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
                return {"status": "SUCCESS", "role": role, "response": displayed_text,
                        "tokens_used": getattr(text, "tokens_used", 0) or len(text) // 4,
                        "usage_source": "provider" if getattr(text, "tokens_used", 0) else "estimated",
                        "conversation_id": getattr(text, "conversation_id", None),
                        "reported_model": getattr(text, "reported_model", None), "backend_used": "cli",
                        "active_skills": [s.name for s in active_skills], "prompt_trace": bundle.trace}
            except Exception as e:
                errors.append(f"CLI: {e}")
                error_code = getattr(e, "code", "CLI_ERROR")
                failed_session = getattr(e, 'conversation_id', None)
                failed_model = getattr(e, 'reported_model', None)
                failed_tokens = getattr(e, 'tokens_used', 0)
                failed_usage_source = getattr(e, 'usage_source', 'unavailable')
                self.last_runtime_error = {"code": error_code, "message": str(e)}

        message = " | ".join(errors) or self.runtime_status()["message"]
        await emit("AGENT_STATUS_CHANGE", {"status": "BLOCKED", "thought": message})
        await emit("AGENT_ERROR", {"message": message})
        return {"status": "FAILED", "role": role, "response": message, "error": message,
                "error_code": error_code,
                "conversation_id": failed_session, "reported_model": failed_model,
                "tokens_used": failed_tokens, "usage_source": failed_usage_source,
                "backend_used": "sdk" if errors and errors[0].startswith("SDK") else "cli" if errors else "unavailable",
                "active_skills": [s.name for s in active_skills]}

    async def dispatch_chat_task(
        self,
        project_id: str,
        role: str,
        message: str,
        workspace_path: str,
        project_context: Optional[Dict[str, Any]] = None,
        conversation_context: str = "",
        attachments: Optional[List[Dict[str, str]]] = None,
        event_callback=None
    ) -> Dict[str, Any]:
        """
        Dispatch a chat-style task for the Unified Team Console.
        Returns structured response with text + code proposals.
        """
        from app.services.console_service import parse_code_proposals

        try:
            bundle = self.prepare_prompt(project_id, role, workspace_path, message, project_context, mode="consultation")
        except (ValueError, OSError) as error:
            return {"status": "FAILED", "role": role, "error": str(error), "response": str(error),
                    "error_code": "PROMPT_INVALID", "code_proposals": [], "tokens_used": 0,
                    "backend_used": "unavailable", "active_skills": []}
        active_skills = bundle.active_skills
        system_instruction = bundle.system

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
            f"This is consultation mode: inspect and propose only; do not edit files or run mutating commands. If you propose code changes, use this format:\n"
            f"**File: path/to/file.ext**\n```language\ncode content\n```\n"
            f"Workspace: {workspace_path}\n"
            f"Respond in Thai or English naturally."
        )
        if len(full_prompt) > bundle.trace["max_characters"]:
            return {"status": "FAILED", "role": role, "response": "Conversation exceeds prompt budget; start a shorter consultation",
                "error": "Conversation exceeds prompt budget", "error_code": "PROMPT_INVALID", "code_proposals": [],
                "tokens_used": 0, "backend_used": "unavailable", "active_skills": []}

        async def emit(event_type, data):
            if event_callback:
                await event_callback(event_type, {"project_id": project_id, "role": role, "timestamp": time.time(), **data})

        await emit("AGENT_PROMPT_READY", {"trace": bundle.trace})
        if self.store:
            self.store.save_prompt_trace(project_id, role, bundle.trace)
        if bundle.trace["warnings"]:
            await emit("AGENT_PROGRESS", {"message": "Prompt warnings: " + "; ".join(bundle.trace["warnings"])})

        errors = []
        response_text = ""
        backend_used = "mock"
        tokens_used = 0

        # 1. Live Antigravity Python SDK Execution (if GEMINI_API_KEY is present and not in mock mode)
        if self.selected_backend() == 'sdk':
            try:
                config = LocalAgentConfig(
                    system_instructions=system_instruction,
                    capabilities=CapabilitiesConfig()
                )
                async with Agent(config) as agent:
                    chat_query = (
                        f"Recent conversation context:\n{conversation_context}\n\n"
                        f"Consultation only: do not edit files or run mutating commands. User message: {message}\n"
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
            except Exception as e:
                errors.append(f"SDK: {e}")

        if not response_text and not errors and self.selected_backend() == 'cli':
            try:
                response_text = await self._run_cli(full_prompt, workspace_path, emit, chat=True)
                self.last_runtime_error = None
                backend_used = "cli"
                tokens_used = getattr(response_text, "tokens_used", 0) or len(response_text) // 4
                response_text = str(response_text)
            except Exception as e:
                errors.append(f"CLI: {e}")
                self.last_runtime_error = {"code": getattr(e, "code", "CLI_ERROR"), "message": str(e)}

        if not response_text and not self.use_mock:
            message = " | ".join(errors) or self.runtime_status()["message"]
            return {"status": "FAILED", "role": role, "response": message, "error": message,
                    "code_proposals": [], "tokens_used": 0, "backend_used": "unavailable", "active_skills": []}

        # Fallback to mock if no agy response
        if not response_text:
            stack = project_context.get("stack_type", "Project") if project_context else "Project"
            response_text = (
                f"[โหมดจำลอง — ไม่มีการทำงานจริง] [{role}] ได้รับข้อความจาก PM แล้วครับ: \"{message}\"\n\n"
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
            "active_skills": [s.name for s in active_skills],
            "prompt_trace": bundle.trace,
        }
