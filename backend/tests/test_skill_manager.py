import os
import shutil
import tempfile
import pytest
from app.services.skill_manager import SkillManager

@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_load_stock_skill():
    manager = SkillManager()
    skill = manager.get_skill("backend-dev")
    assert skill is not None
    assert "backend" in skill.name.lower()
    assert len(skill.instructions) > 50
    assert "workflow" in skill.instructions.lower() or "responsibilit" in skill.instructions.lower()
    assert skill.tier == "stock"

def test_load_skill_by_standard_role_name():
    manager = SkillManager()
    # Should resolve standard role aliases: "Backend", "Frontend", "TechLead", "QA", "DevOps", "Security"
    lead_skill = manager.get_skill("TechLead")
    assert lead_skill is not None
    assert "lead" in lead_skill.name.lower() or "tech" in lead_skill.name.lower()

    qa_skill = manager.get_skill("QA")
    assert qa_skill is not None
    assert "qa" in qa_skill.name.lower() or "test" in qa_skill.name.lower()

def test_project_local_override(temp_project_dir):
    manager = SkillManager()
    # Create project local override in .agents/skills/backend-dev/SKILL.md
    override_dir = os.path.join(temp_project_dir, ".agents", "skills", "backend-dev")
    os.makedirs(override_dir, exist_ok=True)
    override_file = os.path.join(override_dir, "SKILL.md")
    
    with open(override_file, "w", encoding="utf-8") as f:
        f.write("""---
name: backend-dev
title: Custom Backend Specialist
description: Custom project-specific backend rules
allowed_tools: [bash, view_file]
---
# Custom Project Backend Playbook
Always use Python 3.12 and strictly async handlers.
""")

    skill = manager.get_skill("backend-dev", project_path=temp_project_dir)
    assert skill is not None
    assert skill.title == "Custom Backend Specialist"
    assert "Custom Project Backend Playbook" in skill.instructions
    assert skill.tier == "project"

def test_synthesize_agent_prompt():
    manager = SkillManager()
    project_context = {
        "stack": "FastAPI (Python)",
        "project_purpose": "E-Commerce REST API",
        "test_command": "pytest tests/ -v",
        "directory_topology": ["app/", "tests/", "alembic/"]
    }

    full_prompt = manager.synthesize_agent_prompt(
        role="Backend",
        project_context=project_context
    )

    assert "E-Commerce REST API" in full_prompt
    assert "pytest tests/ -v" in full_prompt
    assert "FastAPI (Python)" in full_prompt
    # Must also contain the skill playbook instructions
    assert len(full_prompt) > 200

def test_list_available_skills(temp_project_dir):
    manager = SkillManager()
    skills = manager.list_available_skills(project_path=temp_project_dir)
    assert len(skills) >= 6
    skill_names = [s.name for s in skills]
    assert "tech-lead" in skill_names
    assert "backend-dev" in skill_names
    assert "frontend-dev" in skill_names

def test_save_custom_skill(temp_project_dir):
    manager = SkillManager()
    custom_content = """---
name: data-scientist
title: AI Data Scientist
description: Trains ML models and validates data
allowed_tools: [bash]
---
# Data Science Playbook
Validate datasets before training.
"""
    saved_path = manager.save_custom_skill(
        project_path=temp_project_dir,
        role="data-scientist",
        content=custom_content
    )
    assert os.path.exists(saved_path)

    loaded = manager.get_skill("data-scientist", project_path=temp_project_dir)
    assert loaded is not None
    assert loaded.name == "data-scientist"
    assert loaded.tier == "project"
