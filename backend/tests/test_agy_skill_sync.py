import os
import pytest
from app.services.skill_manager import SkillManager

def test_agy_skills_discovery(tmp_path):
    # Setup mock agy directory
    agy_dir = tmp_path / "mock_gemini_skills"
    tdd_skill_dir = agy_dir / "test-driven-development"
    tdd_skill_dir.mkdir(parents=True)
    (tdd_skill_dir / "SKILL.md").write_text(
        "---\nname: test-driven-development\ntitle: Test-Driven Development\ndescription: TDD workflow\n---\n# TDD Playbook\nWrite tests first.",
        encoding="utf-8"
    )
    
    manager = SkillManager(agy_skills_dir=str(agy_dir))
    skills = manager.list_available_skills()
    
    agy_skills = [s for s in skills if s.tier == "agy"]
    assert len(agy_skills) >= 1
    tdd = next((s for s in agy_skills if s.name == "test-driven-development"), None)
    assert tdd is not None
    assert tdd.title == "Test-Driven Development"
    assert tdd.tier == "agy"

def test_agy_skill_precedence(tmp_path):
    stock_dir = tmp_path / "stock"
    agy_dir = tmp_path / "agy"
    project_dir = tmp_path / "project"
    
    # Create skill in stock, agy, and project
    for base, text in [
        (stock_dir / "backend-dev", "Stock instruction"),
        (agy_dir / "backend-dev", "AGY instruction"),
        (project_dir / ".agents" / "skills" / "backend-dev", "Project instruction"),
    ]:
        base.mkdir(parents=True, exist_ok=True)
        (base / "SKILL.md").write_text(f"---\nname: backend-dev\ntitle: Backend Dev\n---\n{text}", encoding="utf-8")
        
    manager = SkillManager(stock_skills_dir=str(stock_dir), agy_skills_dir=str(agy_dir))
    
    # 1. With project path: project wins
    s_proj = manager.get_skill("backend-dev", project_path=str(project_dir))
    assert s_proj.tier == "project"
    assert "Project instruction" in s_proj.instructions
    
    # 2. Without project path: agy wins over stock
    s_agy = manager.get_skill("backend-dev")
    assert s_agy.tier == "agy"
    assert "AGY instruction" in s_agy.instructions

def test_real_agy_skills_scanned_if_exists():
    real_agy = os.path.expanduser("~/.gemini/config/skills")
    if os.path.exists(real_agy):
        manager = SkillManager()
        skills = manager.list_available_skills()
        agy_skills = [s for s in skills if s.tier == "agy"]
        # Panpan has 22 skills installed in ~/.gemini/config/skills
        assert len(agy_skills) > 0
        names = [s.name for s in agy_skills]
        assert "test-driven-development" in names or "brainstorming" in names or "systematic-debugging" in names
