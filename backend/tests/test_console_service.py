"""Tests for ConsoleService and related utilities."""
import pytest
from app.services.console_service import (
    ConsoleService,
    ConsoleMessage,
    parse_code_proposals,
    parse_target_role,
)


class TestParseTargetRole:
    def test_parse_techlead_mention(self):
        role, msg = parse_target_role("@TechLead explain architecture")
        assert role == "TechLead"
        assert msg == "explain architecture"

    def test_parse_team_mention(self):
        role, msg = parse_target_role("@Team build auth feature")
        assert role == "Team"
        assert msg == "build auth feature"

    def test_parse_frontend_mention(self):
        role, msg = parse_target_role("@Frontend fix login button")
        assert role == "FrontendDev"
        assert msg == "fix login button"

    def test_default_to_techlead(self):
        role, msg = parse_target_role("what is the project status?")
        assert role == "TechLead"
        assert msg == "what is the project status?"

    def test_unknown_mention_defaults_to_techlead(self):
        role, msg = parse_target_role("@Unknown do something")
        assert role == "TechLead"
        assert msg == "@Unknown do something"

    def test_is_actionable_directive(self):
        """
        is_actionable_directive is now DEPRECATED and always returns False.
        Directive detection is exclusively via is_directive=True (Ctrl+Enter) or @all/@team.
        This prevents false positives like "@TechLead ทำเสร็จแล้วเหรอ" triggering a full sprint.
        """
        from app.services.console_service import is_actionable_directive
        # All inputs now return False — auto-detection is disabled
        assert is_actionable_directive("เริ่มลงมือเลย") is False
        assert is_actionable_directive("สร้างระบบ auth และ login") is False
        assert is_actionable_directive("implement checkout flow") is False
        assert is_actionable_directive("start sprint now") is False
        assert is_actionable_directive("สวัสดีครับ") is False
        assert is_actionable_directive("โปรเจกต์นี้มีอะไรบ้าง") is False
        assert is_actionable_directive("hi") is False
        assert is_actionable_directive("") is False


class TestParseCodeProposals:
    def test_parse_file_pattern(self):
        text = """Here is the code:

**File: src/app.py**
```python
def hello():
    return "world"
```
"""
        proposals = parse_code_proposals(text)
        assert len(proposals) == 1
        assert proposals[0]["filepath"] == "src/app.py"
        assert "def hello" in proposals[0]["content"]
        assert proposals[0]["status"] == "pending"

    def test_parse_filename_colon_pattern(self):
        text = """```filename: config.json
{"key": "value"}
```"""
        proposals = parse_code_proposals(text)
        assert len(proposals) == 1
        assert proposals[0]["filepath"] == "config.json"

    def test_no_proposals_in_plain_text(self):
        text = "Just a normal response without any code blocks."
        proposals = parse_code_proposals(text)
        assert len(proposals) == 0


class TestConsoleService:
    def test_add_and_get_messages(self):
        svc = ConsoleService()
        svc.add_message("proj1", "user", "Hello", msg_type="user_chat")
        svc.add_message("proj1", "TechLead", "Hi there!", msg_type="agent_response", role="TechLead")

        history = svc.get_history("proj1")
        assert len(history) == 2
        assert history[0]["sender"] == "user"
        assert history[1]["sender"] == "TechLead"
        assert history[1]["msg_type"] == "agent_response"

    def test_clear_history(self):
        svc = ConsoleService()
        svc.add_message("proj1", "user", "Hello")
        svc.clear_history("proj1")
        assert svc.get_history("proj1") == []

    def test_history_limit(self):
        svc = ConsoleService()
        for i in range(60):
            svc.add_message("proj1", "user", f"Message {i}")
        # get_history default limit is 50
        history = svc.get_history("proj1", limit=10)
        assert len(history) == 10

    def test_message_with_code_proposals(self):
        svc = ConsoleService()
        proposals = [{"filepath": "test.py", "content": "print('hi')", "status": "pending"}]
        msg = svc.add_message(
            "proj1", "BackendDev", "Here is code", 
            msg_type="code_proposal",
            code_proposals=proposals
        )
        assert msg.code_proposals == proposals
        
        history = svc.get_history("proj1")
        assert len(history) == 1
        assert "code_proposals" in history[0]
        assert history[0]["code_proposals"][0]["filepath"] == "test.py"

    def test_get_recent_context(self):
        svc = ConsoleService()
        svc.add_message("proj1", "user", "Build feature X")
        svc.add_message("proj1", "TechLead", "Working on it")
        ctx = svc.get_recent_context("proj1", count=2)
        assert "User:" in ctx or "[PM/User]:" in ctx
        assert "TechLead:" in ctx or "[TechLead]:" in ctx

    def test_isolated_projects(self):
        svc = ConsoleService()
        svc.add_message("proj1", "user", "Message for proj1")
        svc.add_message("proj2", "user", "Message for proj2")
        assert len(svc.get_history("proj1")) == 1
        assert len(svc.get_history("proj2")) == 1

    def test_message_to_dict(self):
        msg = ConsoleMessage(
            sender="TechLead",
            content="Analysis complete",
            msg_type="agent_response",
            role="TechLead"
        )
        d = msg.to_dict()
        assert d["sender"] == "TechLead"
        assert d["msg_type"] == "agent_response"
        assert "timestamp" in d
        assert "message_id" in d
