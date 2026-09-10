import os
import tempfile
import subprocess
import pytest
from app.services.git_service import GitService

def test_git_service_on_git_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo in tmpdir
        subprocess.run(["git", "init"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.name", "Test PM"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "pm@test.local"], cwd=tmpdir, check=True)
        
        # Create initial commit
        f1 = os.path.join(tmpdir, "README.md")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("# Test Project\nInitial readme")
        subprocess.run(["git", "add", "README.md"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmpdir, check=True)
        
        # Modify file and add new untracked file
        with open(f1, "a", encoding="utf-8") as f:
            f.write("\nNew line added by agent")
        f2 = os.path.join(tmpdir, "app.py")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("print('hello world')")
            
        service = GitService()
        status = service.get_git_status(tmpdir)
        
        assert status["has_git"] is True
        assert status["branch"] is not None
        assert status["clean"] is False
        assert len(status["files"]) >= 2
        assert "README.md" in [f["file"] for f in status["files"]]
        assert "New line added by agent" in status["diff"]
        assert len(status["commits"]) == 1
        assert status["commits"][0]["message"] == "initial commit"

def test_git_service_on_non_git_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        service = GitService()
        status = service.get_git_status(tmpdir)
        assert status["has_git"] is False
        assert status["clean"] is True
