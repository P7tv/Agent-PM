"""
ConsoleService: Manages unified conversation history for the Team Console.
Each project has an ordered list of messages forming a chat-like thread.
"""
import time
import uuid
import re
from typing import Dict, List, Any, Optional


class ConsoleMessage:
    """A single message in the console thread."""
    def __init__(
        self,
        sender: str,
        content: str,
        msg_type: str = "user_chat",
        role: Optional[str] = None,
        code_proposals: Optional[List[Dict[str, str]]] = None,
        qa_results: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        project_id: Optional[str] = None,
        active_skills: Optional[List[str]] = None,
    ):
        self.message_id = str(uuid.uuid4())[:8]
        self.project_id = project_id
        self.sender = sender  # "user", "TechLead", "Architect", "FrontendDev", etc. or "system"
        self.content = content
        self.msg_type = msg_type  # directive, agent_response, code_proposal, system, user_chat, qa_result
        self.role = role or sender
        self.code_proposals = code_proposals or []
        self.qa_results = qa_results
        self.attachments = attachments or []
        self.active_skills = active_skills or []
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "message_id": self.message_id,
            "sender": self.sender,
            "content": self.content,
            "msg_type": self.msg_type,
            "role": self.role,
            "timestamp": self.timestamp,
        }
        if self.project_id:
            d["project_id"] = self.project_id
        if self.code_proposals:
            d["code_proposals"] = self.code_proposals
        if self.qa_results:
            d["qa_results"] = self.qa_results
        if self.attachments:
            d["attachments"] = self.attachments
        if self.active_skills:
            d["active_skills"] = self.active_skills
        return d


def parse_code_proposals(text: str) -> List[Dict[str, str]]:
    """
    Extract code proposals from agent response text.
    Looks for fenced code blocks with filename annotations like:
    
    ```filename: path/to/file.py
    code content
    ```
    
    or:
    
    **File: path/to/file.py**
    ```python
    code content
    ```
    """
    proposals = []
    
    # Pattern 1: ```filename: path/to/file
    pattern1 = re.compile(
        r'```(?:filename:\s*|file:\s*)([^\n]+)\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )
    for match in pattern1.finditer(text):
        filepath = match.group(1).strip()
        content = match.group(2).strip()
        if filepath and content:
            proposals.append({"filepath": filepath, "content": content, "status": "pending"})

    # Pattern 2: **File: path** followed by code block
    pattern2 = re.compile(
        r'\*\*(?:File|ไฟล์):\s*`?([^`*\n]+)`?\*\*\s*\n```[a-z]*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )
    for match in pattern2.finditer(text):
        filepath = match.group(1).strip()
        content = match.group(2).strip()
        if filepath and content and not any(p["filepath"] == filepath for p in proposals):
            proposals.append({"filepath": filepath, "content": content, "status": "pending"})
    
    return proposals


def is_actionable_directive(message: str) -> bool:
    """DEPRECATED: Auto-detection removed to prevent false positives.
    Directives must now be explicitly triggered via Ctrl+Enter (is_directive=True).
    """
    return False


def parse_target_role(message: str) -> tuple:
    """
    Parse @Role mention from user message.
    Returns (role, clean_message).
    If no mention found, defaults to "TechLead".
    """
    role_map = {
        "@techlead": "TechLead",
        "@architect": "Architect", 
        "@designer": "Designer",
        "@frontenddev": "FrontendDev",
        "@frontend": "FrontendDev",
        "@backenddev": "BackendDev",
        "@backend": "BackendDev",
        "@qatester": "QATester",
        "@qa": "QATester",
        "@reviewer": "Reviewer",
        "@docwriter": "DocWriter",
        "@team": "Team",
        "@all": "Team",
    }
    
    match = re.match(r'^(@\w+)\s+(.*)', message, re.DOTALL)
    if match:
        mention = match.group(1).lower()
        clean_msg = match.group(2).strip()
        if mention in role_map:
            return role_map[mention], clean_msg
    
    return "TechLead", message


class ConsoleService:
    """Manages conversation history per project with optional SQLite persistence."""
    
    def __init__(self, store: Optional[Any] = None):
        self._histories: Dict[str, List[ConsoleMessage]] = {}
        self.store = store
    
    def add_message(
        self,
        project_id: str,
        sender: str,
        content: str,
        msg_type: str = "user_chat",
        role: Optional[str] = None,
        code_proposals: Optional[List[Dict[str, str]]] = None,
        qa_results: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        active_skills: Optional[List[str]] = None,
    ) -> ConsoleMessage:
        """Add a message to the project's console history."""
        msg = ConsoleMessage(
            sender=sender,
            content=content,
            msg_type=msg_type,
            role=role,
            code_proposals=code_proposals,
            qa_results=qa_results,
            attachments=attachments,
            project_id=project_id,
            active_skills=active_skills
        )
        if project_id not in self._histories:
            self._histories[project_id] = []
        self._histories[project_id].append(msg)
        
        # Persist to SQLite if StateStore is available
        if self.store and project_id:
            try:
                self.store.add_console_message(
                    project_id=project_id,
                    sender=sender,
                    content=content,
                    msg_type=msg_type,
                    role=role,
                    code_proposals=code_proposals,
                    qa_results=qa_results,
                    attachments=attachments,
                    active_skills=active_skills,
                    message_id=msg.message_id,
                    timestamp=msg.timestamp
                )
            except Exception:
                pass
        
        # Keep last 200 messages per project in memory
        if len(self._histories[project_id]) > 200:
            self._histories[project_id] = self._histories[project_id][-200:]
        
        return msg
    
    def get_history(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the conversation history for a project."""
        if self.store:
            try:
                db_msgs = self.store.get_console_messages(project_id, limit=limit)
                if db_msgs:
                    return db_msgs
            except Exception:
                pass
        messages = self._histories.get(project_id, [])
        return [m.to_dict() for m in messages[-limit:]]
    
    def clear_history(self, project_id: str):
        """Clear all messages for a project."""
        self._histories.pop(project_id, None)
        if self.store:
            try:
                self.store.clear_console_messages(project_id)
            except Exception:
                pass
    
    def get_recent_context(self, project_id: str, count: int = 20, max_char_limit: int = 12000) -> str:
        history = self._histories.get(project_id, [])
        if not history and self.store:
            try:
                db_msgs = self.store.get_console_messages(project_id, limit=count)
                history = [
                    ConsoleMessage(
                        sender=m["sender"],
                        content=m["content"],
                        msg_type=m.get("msg_type", "user_chat"),
                        role=m.get("role"),
                        code_proposals=m.get("code_proposals"),
                        qa_results=m.get("qa_results"),
                        attachments=m.get("attachments"),
                        project_id=project_id,
                        active_skills=m.get("active_skills")
                    )
                    for m in db_msgs
                ]
                self._histories[project_id] = history
            except Exception:
                pass

        if not history:
            return ""

        # Get last N messages
        recent = history[-count:]
        
        formatted_msgs = []
        for msg in recent:
            content = msg.content
            if len(content) > 3000:
                content = content[:3000] + "...[truncated]"
            prefix = "User" if msg.sender == "user" else msg.role
            formatted_msgs.append({"prefix": prefix, "content": content})
            
        total_len = 0
        context_lines = []
        
        # Walk backwards to keep newest messages intact, and compact older ones if limit exceeded
        for msg in reversed(formatted_msgs):
            line = f"{msg['prefix']}: {msg['content']}"
            if total_len + len(line) > max_char_limit:
                compact_line = f"{msg['prefix']}: {msg['content'][:80]}... [COMPACTED due to length]"
                context_lines.insert(0, compact_line)
                total_len += len(compact_line)
            else:
                context_lines.insert(0, line)
                total_len += len(line)
                
        return "\n\n".join(context_lines)
