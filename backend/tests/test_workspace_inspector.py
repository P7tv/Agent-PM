import pytest
import os
import tempfile
from app.services.workspace_inspector import WorkspaceInspector

def test_guardrails_reject_invalid_and_dangerous_paths():
    inspector = WorkspaceInspector()
    
    # Non-existent path
    valid, msg, _ = inspector.validate_guardrails("/non/existent/path/xyz_123")
    assert not valid
    assert "does not exist" in msg.lower()
    
    # Dangerous system paths
    valid, msg, _ = inspector.validate_guardrails("/")
    assert not valid
    assert "protected" in msg.lower() or "dangerous" in msg.lower()

    valid, msg, _ = inspector.validate_guardrails("/System")
    assert not valid

def test_guardrails_accept_valid_workspace_and_detect_stack():
    inspector = WorkspaceInspector()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock Node.js project
        pkg_json = os.path.join(tmpdir, "package.json")
        with open(pkg_json, "w") as f:
            f.write('{"name": "my-cool-app", "dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}')
            
        valid, msg, meta = inspector.validate_guardrails(tmpdir)
        assert valid
        assert meta["stack_type"] == "Node.js / React"
        assert "react" in meta["frameworks"]
        assert meta["suggested_name"] == "my-cool-app"

def test_tailored_agent_roster_generation():
    inspector = WorkspaceInspector()
    with tempfile.TemporaryDirectory() as tmpdir:
        reqs = os.path.join(tmpdir, "requirements.txt")
        with open(reqs, "w") as f:
            f.write("fastapi==0.100.0\nuvicorn\npytest\n")
            
        valid, msg, meta = inspector.validate_guardrails(tmpdir)
        assert valid
        assert meta["stack_type"] == "Python"
        
        agents = inspector.generate_tailored_roster(meta)
        roles = [a["role"] for a in agents]
        assert "BackendDev" in roles or "FastAPISpecialist" in roles
        assert any("Python" in a["description"] or "FastAPI" in a["description"] for a in agents)
