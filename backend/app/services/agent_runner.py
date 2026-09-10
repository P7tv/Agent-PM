import asyncio
import time
from typing import Callable, Coroutine, Any, Dict, Optional

# Antigravity SDK
try:
    from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
    HAS_ANTIGRAVITY = True
except ImportError:
    HAS_ANTIGRAVITY = False
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
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock or not HAS_ANTIGRAVITY

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

        if self.use_mock:
            # Deterministic simulation for tests and fallback
            thoughts = [
                f"Analyzing requirements for {role}...",
                f"Examining workspace files in {workspace_path}...",
                "Formulating optimal approach..."
            ]
            for t in thoughts:
                await emit("AGENT_THOUGHT_DELTA", {"thought": t})
                await asyncio.sleep(0.02)
                
            await emit("TOOL_EXECUTION_START", {"tool": "list_files", "args": {"path": workspace_path}})
            await asyncio.sleep(0.02)
            await emit("TOOL_EXECUTION_FINISH", {"tool": "list_files", "result": "Files checked"})
            
            await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
            return {
                "status": "SUCCESS",
                "role": role,
                "response": f"Completed tasks for: {prompt}"
            }

        # Live Antigravity Python SDK Execution with Deep Project Context
        base_instruction = ROLE_PROMPTS.get(role, "You are a helpful software engineering agent.")
        if project_context:
            proj_name = project_context.get("suggested_name") or project_id
            purpose = project_context.get("purpose_summary", "")
            stack = project_context.get("stack_type", "")
            frameworks = ", ".join(project_context.get("frameworks", []))
            test_cmd = project_context.get("test_command", "")
            dirs = ", ".join(project_context.get("directory_structure", [])[:6])

            ctx_header = (
                f"Project: {proj_name}\n"
                f"Workspace Root: {workspace_path}\n"
                f"Project Purpose: {purpose}\n"
                f"Stack & Frameworks: {stack} ({frameworks})\n"
                f"Test Command: {test_cmd}\n"
                f"Key Directories: {dirs}\n"
            )
            system_instruction = f"{ctx_header}\n{base_instruction}\nAlways operate strictly within {workspace_path}."
        else:
            system_instruction = f"{base_instruction} Always operate strictly within {workspace_path}."

        config = LocalAgentConfig(
            system_instructions=system_instruction,
            capabilities=CapabilitiesConfig()
        )
        
        try:
            async with Agent(config) as agent:
                response = await agent.chat(prompt)
                full_text = []
                
                # Stream thoughts if available
                if hasattr(response, "thoughts"):
                    async for thought in response.thoughts:
                        await emit("AGENT_THOUGHT_DELTA", {"thought": str(thought)})
                        
                # Stream tool calls if available
                if hasattr(response, "tool_calls"):
                    async for tool_call in response.tool_calls:
                        await emit("TOOL_EXECUTION_START", {"tool": tool_call.name, "args": tool_call.args})
                        
                # Stream response tokens
                async for token in response:
                    full_text.append(token)
                    
                await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
                return {
                    "status": "SUCCESS",
                    "role": role,
                    "response": "".join(full_text)
                }
        except Exception as e:
            await emit("AGENT_STATUS_CHANGE", {"status": "BLOCKED", "error": str(e)})
            return {
                "status": "ERROR",
                "role": role,
                "error": str(e)
            }
