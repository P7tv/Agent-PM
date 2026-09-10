import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import yaml

@dataclass
class SkillInfo:
    name: str
    title: str
    description: str
    allowed_tools: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    tier: str = "stock"  # "stock" or "project"
    instructions: str = ""
    raw_content: str = ""
    file_path: Optional[str] = None

class SkillManager:
    """
    Manages discovering, caching, parsing, and synthesizing markdown-based SKILL.md playbooks.
    Hierarchy:
      1. Project Local: <project_path>/.agents/skills/<role>/SKILL.md
      2. Stock Built-in: backend/skills/<role>/SKILL.md
      3. Fallback: Core software engineering playbook
    """
    
    ROLE_ALIAS_MAP = {
        "techlead": "tech-lead",
        "tech_lead": "tech-lead",
        "tech-lead": "tech-lead",
        "lead": "tech-lead",
        "pm": "tech-lead",
        "architect": "architect",
        "backend": "backend-dev",
        "backenddev": "backend-dev",
        "backend-dev": "backend-dev",
        "backend_dev": "backend-dev",
        "frontend": "frontend-dev",
        "frontenddev": "frontend-dev",
        "frontend-dev": "frontend-dev",
        "frontend_dev": "frontend-dev",
        "designer": "frontend-dev",
        "qa": "qa-engineer",
        "qatester": "qa-engineer",
        "qa-engineer": "qa-engineer",
        "qa_engineer": "qa-engineer",
        "tester": "qa-engineer",
        "devops": "devops-engineer",
        "devops-engineer": "devops-engineer",
        "devops_engineer": "devops-engineer",
        "security": "security-auditor",
        "security-auditor": "security-auditor",
        "security_auditor": "security-auditor",
        "reviewer": "security-auditor",
        "docwriter": "architect",
        "debugger": "systematic-debugger",
        "systematicdebugger": "systematic-debugger",
        "systematic-debugger": "systematic-debugger",
        "ml": "ml-data-engineer",
        "mlengineer": "ml-data-engineer",
        "ml-data-engineer": "ml-data-engineer",
        "data-scientist": "ml-data-engineer",
        "data-engineer": "ml-data-engineer",
        "dataengineer": "ml-data-engineer"
    }

    def __init__(
        self,
        stock_skills_dir: Optional[str] = None,
        agy_skills_dir: Optional[str] = None
    ):
        if stock_skills_dir:
            self.stock_skills_dir = stock_skills_dir
        else:
            # Default to backend/skills relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.stock_skills_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "skills"))
        
        if agy_skills_dir:
            self.agy_skills_dir = agy_skills_dir
        else:
            # Default to user's Antigravity (agy) config skills directory
            env_agy = os.environ.get("AGY_SKILLS_DIR")
            self.agy_skills_dir = env_agy if env_agy else os.path.expanduser("~/.gemini/config/skills")

        self._cache: Dict[str, SkillInfo] = {}

    def _normalize_role(self, role: str) -> str:
        clean = role.strip().lower().replace(" ", "-")
        return self.ROLE_ALIAS_MAP.get(clean, clean)

    def _parse_skill_file(self, file_path: str, default_tier: str = "stock") -> Optional[SkillInfo]:
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            frontmatter = {}
            body = content

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    yaml_text = parts[1]
                    body = parts[2].strip()
                    try:
                        frontmatter = yaml.safe_load(yaml_text) or {}
                    except Exception:
                        frontmatter = {}

            name = frontmatter.get("name") or os.path.basename(os.path.dirname(file_path))
            title = frontmatter.get("title") or name.replace("-", " ").title()
            description = frontmatter.get("description") or ""
            allowed_tools = frontmatter.get("allowed_tools") or []
            triggers = frontmatter.get("triggers") or []
            tier = frontmatter.get("tier") or default_tier

            return SkillInfo(
                name=name,
                title=title,
                description=description,
                allowed_tools=allowed_tools,
                triggers=triggers,
                tier=tier,
                instructions=body,
                raw_content=content,
                file_path=file_path
            )
        except Exception as err:
            print(f"[SkillManager] Failed to parse skill file {file_path}: {err}")
            return None

    def get_skill(self, role_or_skill_name: str, project_path: Optional[str] = None) -> SkillInfo:
        normalized = self._normalize_role(role_or_skill_name)

        # 1. Check Project Local Override (<project_path>/.agents/skills/<role>/SKILL.md)
        if project_path:
            project_skill_path = os.path.join(project_path, ".agents", "skills", normalized, "SKILL.md")
            if os.path.exists(project_skill_path):
                project_skill = self._parse_skill_file(project_skill_path, default_tier="project")
                if project_skill:
                    return project_skill

        # 2. Check AGY Installed Skills (~/.gemini/config/skills/<skill>/SKILL.md)
        if self.agy_skills_dir and os.path.exists(self.agy_skills_dir):
            agy_skill_path = os.path.join(self.agy_skills_dir, normalized, "SKILL.md")
            if os.path.exists(agy_skill_path):
                agy_skill = self._parse_skill_file(agy_skill_path, default_tier="agy")
                if agy_skill:
                    return agy_skill

        # 3. Check Stock Skills Directory
        stock_skill_path = os.path.join(self.stock_skills_dir, normalized, "SKILL.md")
        if os.path.exists(stock_skill_path):
            stock_skill = self._parse_skill_file(stock_skill_path, default_tier="stock")
            if stock_skill:
                return stock_skill

        # 4. Fallback General Skill
        return SkillInfo(
            name=normalized,
            title=normalized.replace("-", " ").title(),
            description=f"Specialist playbook for {normalized}",
            allowed_tools=["bash", "view_file", "write_file", "edit_file", "grep_search", "list_dir"],
            triggers=[],
            tier="stock",
            instructions=f"# {normalized.replace('-', ' ').title()} Playbook\n\nOperate as a specialist in {normalized}. Follow engineering best practices, verify all changes with tests, and communicate clearly.",
            raw_content=""
        )

    def synthesize_agent_prompt(
        self,
        role: str,
        project_context: Optional[Dict] = None,
        project_path: Optional[str] = None
    ) -> str:
        """
        Synthesizes the unified agent system prompt:
        [80% Stock Playbook / Principles] + [20% Project Context & Constraints]
        """
        skill = self.get_skill(role, project_path=project_path)
        
        prompt_parts = []
        prompt_parts.append(f"You are the **{skill.title}** ({role}).")
        prompt_parts.append(f"Specialty Description: {skill.description}\n")

        # Inject 80% Playbook
        prompt_parts.append("============================================================")
        prompt_parts.append(f"📖 OPERATIONAL PLAYBOOK ({skill.name.upper()} - {skill.tier.upper()} TIER)")
        prompt_parts.append("============================================================")
        prompt_parts.append(skill.instructions)
        prompt_parts.append("")

        # Inject 20% Project Context (if provided)
        if project_context:
            prompt_parts.append("============================================================")
            prompt_parts.append("🔍 REAL-TIME PROJECT CONTEXT & CONSTRAINTS")
            prompt_parts.append("============================================================")
            
            if project_context.get("project_purpose"):
                prompt_parts.append(f"• Project Purpose: {project_context['project_purpose']}")
            if project_context.get("stack"):
                prompt_parts.append(f"• Primary Tech Stack: {project_context['stack']}")
            if project_context.get("test_command"):
                prompt_parts.append(f"• Automated Test Command: {project_context['test_command']}")
            if project_context.get("directory_topology"):
                topo_str = ", ".join(project_context["directory_topology"][:10])
                prompt_parts.append(f"• Key Directories: {topo_str}")
            if project_context.get("has_docker"):
                prompt_parts.append("• Docker: Detected (support containerized commands)")
            prompt_parts.append("")

        prompt_parts.append("============================================================")
        prompt_parts.append("RULES OF ENGAGEMENT:")
        prompt_parts.append("1. Always follow the Operational Playbook strictly.")
        prompt_parts.append("2. Respect the Project Context constraints (do not use conflicting test commands or frameworks).")
        prompt_parts.append("3. Provide clean, production-grade, tested solutions.")

        return "\n".join(prompt_parts)

    def list_available_skills(self, project_path: Optional[str] = None) -> List[SkillInfo]:
        """
        Returns a list of all discoverable skills (stock, agy, and project-local).
        """
        skills_dict: Dict[str, SkillInfo] = {}

        # 1. Scan Stock Skills
        if os.path.exists(self.stock_skills_dir):
            for entry in os.listdir(self.stock_skills_dir):
                skill_dir = os.path.join(self.stock_skills_dir, entry)
                skill_file = os.path.join(skill_dir, "SKILL.md")
                if os.path.isdir(skill_dir) and os.path.exists(skill_file):
                    parsed = self._parse_skill_file(skill_file, default_tier="stock")
                    if parsed:
                        skills_dict[parsed.name] = parsed

        # 2. Scan AGY Installed Skills (~/.gemini/config/skills)
        if self.agy_skills_dir and os.path.exists(self.agy_skills_dir):
            for entry in os.listdir(self.agy_skills_dir):
                skill_dir = os.path.join(self.agy_skills_dir, entry)
                skill_file = os.path.join(skill_dir, "SKILL.md")
                if os.path.isdir(skill_dir) and os.path.exists(skill_file):
                    parsed = self._parse_skill_file(skill_file, default_tier="agy")
                    if parsed:
                        skills_dict[parsed.name] = parsed

        # 3. Scan Project Local Skills (Overwriting if same name)
        if project_path:
            project_skills_dir = os.path.join(project_path, ".agents", "skills")
            if os.path.exists(project_skills_dir):
                for entry in os.listdir(project_skills_dir):
                    skill_dir = os.path.join(project_skills_dir, entry)
                    skill_file = os.path.join(skill_dir, "SKILL.md")
                    if os.path.isdir(skill_dir) and os.path.exists(skill_file):
                        parsed = self._parse_skill_file(skill_file, default_tier="project")
                        if parsed:
                            skills_dict[parsed.name] = parsed

        return list(skills_dict.values())

    def save_custom_skill(self, project_path: str, role: str, content: str) -> str:
        """
        Saves a custom SKILL.md file into <project_path>/.agents/skills/<role>/SKILL.md
        """
        normalized = self._normalize_role(role)
        target_dir = os.path.join(project_path, ".agents", "skills", normalized)
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, "SKILL.md")
        
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return target_file
