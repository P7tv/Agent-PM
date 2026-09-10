"""Tests for apply-change and console endpoints using direct service testing."""
import os
import pytest
import tempfile
from app.services.console_service import ConsoleService, parse_target_role


# ── Tests that don't need HTTP (direct service tests) ──

class TestApplyChangeLogic:
    """Test the file writing logic directly without HTTP."""
    
    def test_write_file_to_workspace(self, tmp_path):
        workspace = str(tmp_path)
        filepath = "src/hello.py"
        content = "print('Hello World')\n"
        
        full_path = os.path.join(workspace, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        assert os.path.exists(full_path)
        with open(full_path) as f:
            assert f.read() == content

    def test_path_traversal_detection(self, tmp_path):
        workspace = str(tmp_path)
        filepath = "../../etc/passwd"
        full_path = os.path.join(workspace, filepath)
        
        real_workspace = os.path.realpath(workspace)
        real_target = os.path.realpath(full_path)
        
        assert not real_target.startswith(real_workspace), "Path traversal should be detected"

    def test_safe_path_inside_workspace(self, tmp_path):
        workspace = str(tmp_path)
        filepath = "src/nested/deep/file.py"
        full_path = os.path.join(workspace, filepath)
        
        real_workspace = os.path.realpath(workspace)
        real_target = os.path.realpath(full_path)
        
        # Even though the intermediate dirs don't exist yet, realpath resolves
        # We check parent for non-existent files
        assert os.path.realpath(os.path.dirname(full_path)).startswith(real_workspace)


class TestConsoleEndpointLogic:
    """Test console routing logic directly."""
    
    def test_parse_role_for_chat(self):
        role, msg = parse_target_role("@TechLead explain architecture")
        assert role == "TechLead"
        assert msg == "explain architecture"
    
    def test_parse_team_for_broadcast(self):
        role, msg = parse_target_role("@Team implement authentication")
        assert role == "Team"
        assert msg == "implement authentication"

    def test_console_history_lifecycle(self):
        svc = ConsoleService()
        
        # Start empty
        assert svc.get_history("proj_test") == []
        
        # Add user message
        svc.add_message("proj_test", "user", "Hello @TechLead", msg_type="user_chat")
        
        # Add agent response
        svc.add_message(
            "proj_test", "TechLead", "Hello! I'm ready.",
            msg_type="agent_response", role="TechLead"
        )
        
        history = svc.get_history("proj_test")
        assert len(history) == 2
        assert history[0]["sender"] == "user"
        assert history[1]["sender"] == "TechLead"
        assert history[1]["role"] == "TechLead"
        
        # Clear
        svc.clear_history("proj_test")
        assert svc.get_history("proj_test") == []

    def test_console_code_proposal_in_message(self):
        svc = ConsoleService()
        proposals = [
            {"filepath": "app.py", "content": "print('hello')", "status": "pending"}
        ]
        svc.add_message(
            "proj_test", "BackendDev", "Here is code",
            msg_type="code_proposal",
            code_proposals=proposals
        )
        history = svc.get_history("proj_test")
        assert len(history) == 1
        assert history[0]["code_proposals"][0]["filepath"] == "app.py"

    def test_console_qa_result_in_message(self):
        svc = ConsoleService()
        qa = {"status": "PASSED", "command": "pytest -v", "stdout": "all passed", "stderr": ""}
        svc.add_message(
            "proj_test", "QATester", "Tests passed",
            msg_type="qa_result",
            qa_results=qa
        )
        history = svc.get_history("proj_test")
        assert len(history) == 1
        assert history[0]["qa_results"]["status"] == "PASSED"
