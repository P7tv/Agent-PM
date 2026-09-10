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
            "test_command": None,
            "has_git": os.path.exists(os.path.join(path, ".git")),
            "has_docker": False,
            "purpose_summary": "",
            "directory_structure": [],
            "file_count": 0,
            "summary": ""
        }

        # 1. Parse README for Purpose Summary
        for r_name in ["README.md", "readme.md", "README", "README.txt", "readme.markdown"]:
            r_path = os.path.join(path, r_name)
            if os.path.exists(r_path):
                try:
                    with open(r_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw_readme = f.read(3000)
                        lines = [l.strip() for l in raw_readme.split("\n") if l.strip()]
                        # Extract first header and first non-header description
                        title = ""
                        desc = ""
                        for line in lines:
                            if line.startswith("#") and not title:
                                title = line.lstrip("#").strip()
                            elif not line.startswith("#") and not line.startswith("!") and not desc:
                                desc = line.strip()
                        if title and desc:
                            meta["purpose_summary"] = f"{title}: {desc}"
                        elif title:
                            meta["purpose_summary"] = title
                        elif desc:
                            meta["purpose_summary"] = desc
                        else:
                            meta["purpose_summary"] = lines[0] if lines else ""
                        break
                except Exception:
                    pass

        # 2. Check Docker
        if (
            os.path.exists(os.path.join(path, "Dockerfile"))
            or os.path.exists(os.path.join(path, "docker-compose.yml"))
            or os.path.exists(os.path.join(path, "docker-compose.yaml"))
        ):
            meta["has_docker"] = True

        # 3. Check Node.js / JavaScript
        pkg_json_path = os.path.join(path, "package.json")
        if os.path.exists(pkg_json_path):
            meta["stack_type"] = "Node.js"
            try:
                with open(pkg_json_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    if "name" in pkg_data and pkg_data["name"]:
                        meta["suggested_name"] = pkg_data["name"]
                    
                    # Test commands from package scripts
                    scripts = pkg_data.get("scripts", {})
                    if "test" in scripts and scripts["test"]:
                        meta["test_command"] = scripts["test"]
                    
                    deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                    for framework in ["react", "next", "vue", "nuxt", "svelte", "express", "fastify", "tailwind", "vite"]:
                        if any(framework in d.lower() for d in deps):
                            meta["frameworks"].append(framework)
                            
                    if "next" in meta["frameworks"] or "react" in meta["frameworks"]:
                        meta["stack_type"] = "Node.js / React"
                    elif "vue" in meta["frameworks"]:
                        meta["stack_type"] = "Node.js / Vue"
                        
                    test_script = scripts.get("test", "").lower()
                    if "vitest" in deps or "vitest" in test_script:
                        meta["test_runner"] = "vitest"
                    elif "jest" in deps or "jest" in test_script:
                        meta["test_runner"] = "jest"
            except Exception:
                pass

        # 4. Check Python
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
                meta["test_command"] = "pytest tests/ -v"

        # 5. Scan Directory Topology (depth <= 2)
        dirs_found = []
        try:
            for root, dirs, files in os.walk(path):
                rel_root = os.path.relpath(root, path)
                # Filter out ignore folders
                dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".next", ".cache"]]
                if rel_root != ".":
                    parts = rel_root.split(os.sep)
                    if len(parts) <= 2:
                        dirs_found.append(rel_root.replace(os.sep, "/") + "/")
                if len(dirs_found) >= 20:
                    break
        except Exception:
            pass
        meta["directory_structure"] = dirs_found

        # Count visible files (max 200 for fast responsiveness)
        count = 0
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".next", ".cache"]]
            count += len(files)
            if count > 200:
                break
        meta["file_count"] = count

        if not meta["purpose_summary"]:
            meta["purpose_summary"] = f"{meta['stack_type']} project with {len(dirs_found)} directories and ~{count} active files."

        meta["summary"] = f"{meta['purpose_summary']} (Stack: {meta['stack_type']}, Tests: {meta.get('test_runner') or 'none'})"

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
                    "role": "TechLead",
                    "title": "Lead Software Engineer & Tech Lead",
                    "description": f"Coordinates team execution for {stack} application, synthesizes status standups, resolves blockers, and reports directly to the PM."
                },
                {
                    "role": "Architect",
                    "title": "Lead Software Architect",
                    "description": f"Decomposes requirements for {stack} application into modular components and state stores."
                },
                {
                    "role": "Designer",
                    "title": "UI/UX Designer",
                    "description": "Creates design tokens, color palettes, responsive layouts, and component specifications."
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
                    "role": "TechLead",
                    "title": "Staff Python Engineer & Tech Lead",
                    "description": "Orchestrates Python backend workflow, conducts daily standup briefings, resolves blockers, and liaises with PM."
                },
                {
                    "role": "Architect",
                    "title": "Python Solutions Architect",
                    "description": "Plans data models, Pydantic schemas, dependency structures, and service boundaries."
                },
                {
                    "role": "Designer",
                    "title": "UI/UX Designer",
                    "description": "Designs interface layouts, styling tokens, and visual component specifications."
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
                    "role": "TechLead",
                    "title": "Principal Engineer & Tech Lead",
                    "description": "Supervises project architecture, monitors team health, delivers standup briefings, and coordinates with PM."
                },
                {
                    "role": "Architect",
                    "title": "Systems Architect",
                    "description": "Analyzes codebase layout and breaks high-level features into discrete tasks."
                },
                {
                    "role": "Designer",
                    "title": "UI/UX Designer",
                    "description": "Creates design specifications, color systems, and layout blueprints."
                },
                {
                    "role": "FrontendDev",
                    "title": "UI Engineer",
                    "description": "Implements layouts and user interface components."
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
