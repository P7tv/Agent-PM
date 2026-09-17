import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)

def test_get_skills_includes_tiers():
    response = client.get("/api/skills")
    assert response.status_code == 200
    skills = response.json()
    assert isinstance(skills, list)
    assert len(skills) > 0
    tiers = {s.get("tier") for s in skills}
    # At least stock tier exists, and agy tier if installed
    assert "stock" in tiers or "agy" in tiers
    for s in skills:
        assert "name" in s
        assert "title" in s
        assert "tier" in s

def test_download_online_skill_route(tmp_path, monkeypatch):
    from app.api import routes
    monkeypatch.setattr(routes.skill_manager, 'stock_skills_dir', str(tmp_path / 'stock'))
    # Mock download_online_skill in skill_manager
    mock_md = "---\nname: mock-skill\ntitle: Mock Skill\ndescription: A mock skill\ntier: project\n---\n# Instructions"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = mock_md.encode("utf-8")
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        
        # Test download with target 'stock'
        res = client.post("/api/skills/download", json={
            "url": "https://raw.githubusercontent.com/user/repo/main/mock-skill/SKILL.md",
            "skill_name": "mock-downloaded-skill",
            "target": "stock"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert "mock-downloaded-skill" in data["skill"]["name"]

def test_assign_agent_skill_route():
    import os
    workspace_dir = "/tmp/test-assign-proj"
    os.makedirs(workspace_dir, exist_ok=True)

    proj_res = client.post("/api/projects", json={
        "project_id": "test-assign-proj",
        "name": "test-assign-proj",
        "workspace_path": workspace_dir
    })
    assert proj_res.status_code == 200
    proj_id = proj_res.json()["project_id"]
    
    res = client.post(f"/api/projects/{proj_id}/agents/TechLead/assign-skill", json={
        "skill_name": "security-auditor"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["role"] == "TechLead"
    assert data["skill_name"] == "security-auditor"
    assert "security-auditor" in data.get("equipped_skills", [])
    assert data.get("skill_mode") == "MANUAL"

    # Verify GET /api/projects/{proj_id}/skills returns equipped_skills
    skills_res = client.get(f"/api/projects/{proj_id}/skills")
    assert skills_res.status_code == 200
    all_ag_skills = skills_res.json()
    tl_skill = next((a for a in all_ag_skills if a["role"] == "TechLead"), None)
    assert tl_skill is not None
    assert "security-auditor" in tl_skill["equipped_skills"]
    assert tl_skill["skill_mode"] == "MANUAL"
