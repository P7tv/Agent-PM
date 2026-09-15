import os
import subprocess
from typing import Dict, Any, List, Optional

class GitService:
    def get_git_status(self, workspace_path: str) -> Dict[str, Any]:
        """
        Gathers live git branch, status, diff, and recent commits for a project workspace.
        """
        if not os.path.exists(workspace_path):
            return {"has_git": False, "error": "Workspace directory does not exist"}

        git_dir = os.path.join(workspace_path, ".git")
        if not os.path.exists(git_dir):
            return {
                "has_git": False,
                "workspace_path": workspace_path,
                "branch": None,
                "clean": True,
                "files": [],
                "diff": "",
                "commits": []
            }

        try:
            # 1. Current branch
            res_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "main"

            # 2. Git status --porcelain
            res_status = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            status_lines = res_status.stdout.splitlines() if res_status.returncode == 0 else []
            files = []
            for line in status_lines:
                if len(line) >= 3:
                    code = line[:2].strip()
                    file_name = line[3:].strip()
                    status_type = "MODIFIED"
                    if "A" in code or "??" in code:
                        status_type = "ADDED"
                    elif "D" in code:
                        status_type = "DELETED"
                    elif "M" in code:
                        status_type = "MODIFIED"
                    files.append({
                        "file": file_name,
                        "code": code,
                        "status": status_type
                    })

            # 3. Git diff (unstaged + staged)
            res_diff = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Fallback to unstaged diff if HEAD fails (e.g. fresh repo with no commits)
            diff_text = res_diff.stdout if res_diff.returncode == 0 else ""
            if not diff_text:
                res_diff_unstaged = subprocess.run(
                    ["git", "diff"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                diff_text = res_diff_unstaged.stdout if res_diff_unstaged.returncode == 0 else ""

            # 4. Recent commits (up to 25 for rich graph history)
            res_log = subprocess.run(
                ["git", "log", "-n", "25", "--pretty=format:%h|%an|%ar|%s"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            commits = []
            if res_log.returncode == 0 and res_log.stdout.strip():
                for c_line in res_log.stdout.strip().split("\n"):
                    parts = c_line.split("|", 3)
                    if len(parts) == 4:
                        commits.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "time": parts[2],
                            "message": parts[3]
                        })

            return {
                "has_git": True,
                "workspace_path": workspace_path,
                "branch": branch,
                "clean": len(files) == 0,
                "files": files,
                "diff": diff_text,
                "commits": commits
            }
        except subprocess.TimeoutExpired:
            return {"has_git": True, "error": "Git command timed out"}
        except Exception as e:
            return {"has_git": False, "error": str(e)}

    def init_repository(self, workspace_path: str) -> Dict[str, Any]:
        """Initializes a git repository if one does not exist."""
        try:
            res = subprocess.run(["git", "init"], cwd=workspace_path, capture_output=True, text=True, timeout=5)
            return {
                "success": res.returncode == 0,
                "message": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_patch(self, workspace_path: str) -> str:
        """Returns full git diff/patch text for the workspace."""
        if not os.path.exists(workspace_path):
            return ""
        try:
            res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout
            res_unstaged = subprocess.run(
                ["git", "diff"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            return res_unstaged.stdout if res_unstaged.returncode == 0 else ""
        except Exception:
            return ""

    def get_remotes(self, workspace_path: str) -> List[Dict[str, str]]:
        """Returns list of configured git remotes with their URLs."""
        if not os.path.exists(workspace_path):
            return []
        try:
            res = subprocess.run(
                ["git", "remote", "-v"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            remotes = []
            seen = set()
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        name, url = parts[0], parts[1]
                        if name not in seen:
                            seen.add(name)
                            remotes.append({"name": name, "url": url})
            return remotes
        except Exception:
            return []

    def set_remote(self, workspace_path: str, name: str, url: str) -> Dict[str, Any]:
        """Adds or updates a git remote URL."""
        if not os.path.exists(workspace_path):
            return {"success": False, "message": "Workspace does not exist"}
        try:
            res_check = subprocess.run(
                ["git", "remote", "get-url", name],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if res_check.returncode == 0:
                cmd = ["git", "remote", "set-url", name, url]
            else:
                cmd = ["git", "remote", "add", name, url]
            res = subprocess.run(cmd, cwd=workspace_path, capture_output=True, text=True, timeout=5)
            return {
                "success": res.returncode == 0,
                "name": name,
                "url": url,
                "message": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def git_push(self, workspace_path: str, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        """Pushes current branch to remote repository."""
        if not os.path.exists(workspace_path):
            return {"success": False, "message": "Workspace does not exist"}
        try:
            cmd = ["git", "push", remote]
            if branch:
                cmd.append(branch)
            res = subprocess.run(cmd, cwd=workspace_path, capture_output=True, text=True, timeout=30)
            return {
                "success": res.returncode == 0,
                "message": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "Git push timed out after 30 seconds."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def git_pull(self, workspace_path: str, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        """Pulls latest changes from remote repository."""
        if not os.path.exists(workspace_path):
            return {"success": False, "message": "Workspace does not exist"}
        try:
            cmd = ["git", "pull", remote]
            if branch:
                cmd.append(branch)
            res = subprocess.run(cmd, cwd=workspace_path, capture_output=True, text=True, timeout=30)
            return {
                "success": res.returncode == 0,
                "message": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "Git pull timed out after 30 seconds."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_branches(self, workspace_path: str) -> List[Dict[str, Any]]:
        """Lists local git branches with current branch indicated."""
        if not os.path.exists(workspace_path):
            return []
        try:
            res = subprocess.run(
                ["git", "branch", "--no-color"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            branches = []
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    is_current = clean_line.startswith("*")
                    b_name = clean_line.lstrip("*").strip()
                    branches.append({"name": b_name, "is_current": is_current})
            return branches
        except Exception:
            return []

    def create_branch(self, workspace_path: str, branch_name: str, checkout: bool = True) -> Dict[str, Any]:
        """Creates a new git branch and optionally checks it out."""
        if not os.path.exists(workspace_path):
            return {"success": False, "message": "Workspace does not exist"}
        try:
            cmd = ["git", "checkout", "-b", branch_name] if checkout else ["git", "branch", branch_name]
            res = subprocess.run(cmd, cwd=workspace_path, capture_output=True, text=True, timeout=5)
            return {
                "success": res.returncode == 0,
                "branch": branch_name,
                "message": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def switch_branch(self, workspace_path: str, branch_name: str) -> Dict[str, Any]:
        """Switches to an existing git branch."""
        if not os.path.exists(workspace_path):
            return {"success": False, "message": "Workspace does not exist"}
        try:
            res = subprocess.run(["git", "checkout", branch_name], cwd=workspace_path, capture_output=True, text=True, timeout=5)
            return {
                "success": res.returncode == 0,
                "branch": branch_name,
                "message": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

