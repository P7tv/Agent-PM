import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.skill_manager import SkillManager

def test_normalize_github_blob_url():
    manager = SkillManager()
    github_blob = "https://github.com/user/repo/blob/main/skills/fastapi/SKILL.md"
    raw_url = manager.normalize_download_url(github_blob)
    assert raw_url == "https://raw.githubusercontent.com/user/repo/main/skills/fastapi/SKILL.md"

    # Direct raw url remains unchanged
    raw_input = "https://raw.githubusercontent.com/user/repo/main/skills/fastapi/SKILL.md"
    assert manager.normalize_download_url(raw_input) == raw_input

def test_download_online_skill_to_project(tmp_path):
    manager = SkillManager(stock_skills_dir=str(tmp_path / "stock"))
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    
    mock_md = "---\nname: fastapi-pro\ntitle: FastAPI Pro\ndescription: Expert in async FastAPI\n---\n# FastAPI Pro\nBuild performant endpoints."
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = mock_md.encode("utf-8")
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        skill = manager.download_online_skill(
            url="https://raw.githubusercontent.com/user/repo/main/skills/fastapi/SKILL.md",
            skill_name="fastapi-pro",
            target="project",
            project_path=str(project_dir)
        )
        
        assert skill.name == "fastapi-pro"
        assert skill.tier == "project"
        assert "FastAPI Pro" in skill.title
        assert "Expert in async FastAPI" in skill.description
        
        target_file = project_dir / ".agents" / "skills" / "fastapi-pro" / "SKILL.md"
        assert target_file.exists()
        assert "Build performant endpoints" in target_file.read_text(encoding="utf-8")

def test_download_online_skill_size_limit(tmp_path):
    manager = SkillManager()
    # Large payload exceeding 512 KB
    giant_content = b"a" * (600 * 1024)
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = giant_content
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        with pytest.raises(ValueError, match="exceeds maximum limit"):
            manager.download_online_skill(
                url="https://raw.githubusercontent.com/user/repo/main/giant/SKILL.md",
                skill_name="giant-skill",
                target="stock"
            )
