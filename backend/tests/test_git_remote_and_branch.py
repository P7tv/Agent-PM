"""Tests for git remotes, branch management, and operations."""
import os
import subprocess
import pytest
from app.services.git_service import GitService


@pytest.fixture
def temp_git_repo(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    git_svc = GitService()
    git_svc.init_repository(str(repo_dir))
    
    # Configure git test user
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(repo_dir))
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo_dir))

    # Create initial commit
    dummy_file = repo_dir / "README.md"
    dummy_file.write_text("# Hello World")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir))
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir))

    return git_svc, str(repo_dir)


def test_git_branch_operations(temp_git_repo):
    git_svc, repo_dir = temp_git_repo

    branches = git_svc.list_branches(repo_dir)
    assert len(branches) >= 1
    current = [b for b in branches if b["is_current"]][0]
    assert current["name"] in ["main", "master"]

    # Create new branch
    res = git_svc.create_branch(repo_dir, "feature/login", checkout=True)
    assert res["success"] is True

    branches_after = git_svc.list_branches(repo_dir)
    current_after = [b for b in branches_after if b["is_current"]][0]
    assert current_after["name"] == "feature/login"

    # Switch back
    res_switch = git_svc.switch_branch(repo_dir, current["name"])
    assert res_switch["success"] is True


def test_git_remote_operations(temp_git_repo):
    git_svc, repo_dir = temp_git_repo

    remotes = git_svc.get_remotes(repo_dir)
    assert len(remotes) == 0

    res_add = git_svc.set_remote(repo_dir, "origin", "https://github.com/org/repo.git")
    assert res_add["success"] is True

    remotes_after = git_svc.get_remotes(repo_dir)
    assert len(remotes_after) == 1
    assert remotes_after[0]["name"] == "origin"
    assert remotes_after[0]["url"] == "https://github.com/org/repo.git"
