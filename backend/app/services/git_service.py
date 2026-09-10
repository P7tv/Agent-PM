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
