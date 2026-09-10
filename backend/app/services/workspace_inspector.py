import os
import json
from typing import Tuple, Dict, Any, List

DANGEROUS_PATHS = {
    "/",
    "/System",
    "/System/Library",
    "/Library",
    "/Applications",
    "/bin",
    "/sbin",
    "/usr",
    "/usr/bin",
    "/usr/sbin",
    "/etc",
    "/private",
    "/dev",
    "/Volumes"
}

class WorkspaceInspector:
    def __init__(self):
        self.home_dir = os.path.expanduser("~")

    def validate_guardrails(self, path_str: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates if the provided path is safe and is a legitimate project workspace.
        Returns (is_valid, message, metadata).
        """
        if not path_str or not isinstance(path_str, str):
            return False, "Workspace path cannot be empty.", {}

        resolved_path = os.path.abspath(os.path.expanduser(path_str.strip()))

        # 1. Existence check
        if not os.path.exists(resolved_path):
            return False, f"Directory does not exist: '{resolved_path}'", {}

        # 2. Directory check
        if not os.path.isdir(resolved_path):
            return False, f"Path is a file, not a directory: '{resolved_path}'", {}

        # 3. Protected system directories guardrail
        if resolved_path in DANGEROUS_PATHS or any(resolved_path.startswith(dp + "/") for dp in ["/System", "/private", "/dev"]):
            return False, f"Protected system directory cannot be used as a workspace: '{resolved_path}'", {}

        # 4. User home root guardrail (avoid accidental recursive scans of whole home dir)
        if resolved_path == self.home_dir:
            return False, "Cannot select entire user home folder as workspace. Please select a specific project directory.", {}

        # 5. Permission check
        if not os.access(resolved_path, os.R_OK | os.W_OK):
            return False, f"Directory does not have read/write permissions: '{resolved_path}'", {}

        # 6. Deep inspection of workspace files and stack
        meta = self._inspect_codebase(resolved_path)
        return True, "Workspace validated successfully", meta

    def _inspect_codebase(self, path: str) -> Dict[str, Any]:
        meta = {
            "path": path,
            "suggested_name": os.path.basename(path) or "Project",
            "stack_type": "Generic Project",
            "frameworks": [],
            "test_runner": None,
            "has_git": os.path.exists(os.path.join(path, ".git")),
            "file_count": 0,
            "summary": ""
        }

        # Check Node.js / JavaScript
        pkg_json_path = os.path.join(path, "package.json")
        if os.path.exists(pkg_json_path):
            meta["stack_type"] = "Node.js"
            try:
                with open(pkg_json_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    if "name" in pkg_data and pkg_data["name"]:
                        meta["suggested_name"] = pkg_data["name"]
                    
                    deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                    for framework in ["react", "next", "vue", "nuxt", "svelte", "express", "fastify", "tailwind", "vite"]:
                        if any(framework in d.lower() for d in deps):
                            meta["frameworks"].append(framework)
                            
                    if "next" in meta["frameworks"] or "react" in meta["frameworks"]:
                        meta["stack_type"] = "Node.js / React"
                    elif "vue" in meta["frameworks"]:
                        meta["stack_type"] = "Node.js / Vue"
                        
                    if "jest" in deps or "vitest" in deps:
                        meta["test_runner"] = "vitest" if "vitest" in deps else "jest"
            except Exception:
                pass

        # Check Python
        reqs_path = os.path.join(path, "requirements.txt")
        pyproject_path = os.path.join(path, "pyproject.toml")
        if os.path.exists(reqs_path) or os.path.exists(pyproject_path):
            meta["stack_type"] = "Python"
            content = ""
            if os.path.exists(reqs_path):
                try:
                    with open(reqs_path, "r", encoding="utf-8") as f:
                        content += f.read().lower()
                except Exception:
                    pass
            if os.path.exists(pyproject_path):
                try:
                    with open(pyproject_path, "r", encoding="utf-8") as f:
                        content += f.read().lower()
                except Exception:
                    pass

            for py_framework in ["fastapi", "django", "flask", "pytest", "torch", "pandas"]:
                if py_framework in content:
                    meta["frameworks"].append(py_framework)
            if "pytest" in content:
                meta["test_runner"] = "pytest"

        # Count visible files (max 200 for fast responsiveness)
        count = 0
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__", "dist", "build"]]
            count += len(files)
            if count > 200:
                break
        meta["file_count"] = count
        meta["summary"] = f"Detected {meta['stack_type']} codebase with ~{count} active files."

        return meta

    def generate_tailored_roster(self, meta: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Dynamically tailors 5-7 specialized agent roles and system instructions
        tailored directly to the detected codebase stack.
        """
        stack = meta.get("stack_type", "Generic")
        frameworks = meta.get("frameworks", [])

        if "Node.js" in stack or "React" in stack:
            return [
                {
                    "role": "Architect",
                    "title": "Lead Software Architect",
                    "description": f"Decomposes requirements for {stack} application into modular components and state stores."
                },
                {
                    "role": "FrontendDev",
                    "title": "Frontend & UI Engineer",
                    "description": "Builds responsive React/HTML components, CSS design tokens, and client interactions."
                },
                {
                    "role": "BackendDev",
                    "title": "Full-Stack / API Dev",
                    "description": "Implements server routes, data fetching, API integrations, and database logic."
                },
                {
                    "role": "QATester",
                    "title": "Test & Quality Engineer",
                    "description": f"Runs automated test runners ({meta.get('test_runner') or 'npm test'}) and validates DOM/API outputs."
                },
                {
                    "role": "Reviewer",
                    "title": "Code Quality & Security Auditor",
                    "description": "Performs git diff audits, lint checks, security reviews, and release notes."
                },
                {
                    "role": "DocWriter",
                    "title": "Technical Writer",
                    "description": "Maintains README documentation, setup guides, and component references."
                }
            ]
        elif "Python" in stack:
            return [
                {
                    "role": "Architect",
                    "title": "Python Solutions Architect",
                    "description": "Plans data models, Pydantic schemas, dependency structures, and service boundaries."
                },
                {
                    "role": "BackendDev",
                    "title": "Python Core Engineer",
                    "description": f"Implements Python backend logic, endpoints ({', '.join(frameworks) if frameworks else 'FastAPI/REST'}), and services."
                },
                {
                    "role": "FrontendDev",
                    "title": "Interface & Client Specialist",
                    "description": "Builds templates, client scripts, frontend integration, and dashboard views."
                },
                {
                    "role": "QATester",
                    "title": "Pytest Automation Engineer",
                    "description": f"Executes pytest test suites, catches regressions, and executes self-healing test loops."
                },
                {
                    "role": "Reviewer",
                    "title": "Staff Code Reviewer",
                    "description": "Verifies PEP8 compliance, async performance, type annotations, and git diffs."
                },
                {
                    "role": "DocWriter",
                    "title": "Documentation Engineer",
                    "description": "Updates docstrings, API specifications, and usage instructions."
                }
            ]
        else:
            return [
                {
                    "role": "Architect",
                    "title": "Systems Architect",
                    "description": "Analyzes codebase layout and breaks high-level features into discrete tasks."
                },
                {
                    "role": "FrontendDev",
                    "title": "UI Engineer",
                    "description": "Designs layouts and user interface components."
                },
                {
                    "role": "BackendDev",
                    "title": "Core Systems Engineer",
                    "description": "Implements business logic, algorithms, and file operations."
                },
                {
                    "role": "QATester",
                    "title": "Verification & QA Specialist",
                    "description": "Executes automated tests and regression verification."
                },
                {
                    "role": "Reviewer",
                    "title": "Code Reviewer",
                    "description": "Performs code audits, security checks, and sprint release summaries."
                },
                {
                    "role": "DocWriter",
                    "title": "Documentation Writer",
                    "description": "Updates documentation and changelogs."
                }
            ]
