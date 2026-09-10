# AGY Skills Sync & Online Skill Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate local Antigravity (`agy`) installed skills (`~/.gemini/config/skills/`) and an Online GitHub/URL Skill Downloader into My PM's agent orchestration engine and UI.

**Architecture:** 
- `SkillManager` is upgraded with a 4-tier discovery engine (`project` > `agy` > `stock` > `fallback`) auto-discovering all 22+ local AGY skills at runtime without server restart.
- An online skill downloader and sanitizer engine fetches, validates, and writes remote GitHub/raw markdown playbooks to project or stock destinations.
- REST endpoints expose download, catalogue browsing, and role-to-skill assignment.
- Frontend Focus Room receives a unified "Skill Hub & AGY Sync" modal and dynamic assignment selector.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, PyYAML, urllib/requests, React 18, Vite, Lucide Icons.

## Global Constraints
- Do not break existing 30 passing backend tests.
- Support both `~/.gemini/config/skills/` and custom `AGY_SKILLS_DIR` env vars.
- Strict size limit of 512 KB on remote skill downloads.
- URL conversion support: `github.com/.../blob/...` automatically converted to raw GitHub user content URL.
- Retain high-contrast Dark & Light mode compatibility in the UI.

---

### Task 1: AGY Skills Discovery & Multi-Tier Resolution in `SkillManager`

**Files:**
- Modify: `backend/app/services/skill_manager.py`
- Test: `backend/tests/test_agy_skill_sync.py`

**Interfaces:**
- `SkillManager(stock_skills_dir: Optional[str] = None, agy_skills_dir: Optional[str] = None)`
- `list_available_skills(project_path: Optional[str] = None) -> List[SkillInfo]` returns skills from `stock`, `agy`, and `project` with correct `tier` properties.
- `get_skill(role_or_skill_name: str, project_path: Optional[str] = None) -> SkillInfo` respects precedence: `project` > `agy` > `stock` > `fallback`.

- [ ] **Step 1: Write the failing test for AGY skill discovery and tier precedence**

```python
# backend/tests/test_agy_skill_sync.py
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
    tdd = next(s for s in agy_skills if s.name == "test-driven-development")
    assert tdd.title == "Test-Driven Development"
    assert tdd.tier == "agy"

def test_agy_skill_precedence(tmp_path):
    stock_dir = tmp_path / "stock"
    agy_dir = tmp_path / "agy"
    project_dir = tmp_path / "project"
    
    # Create skill in stock, agy, and project
    for base, tier, text in [
        (stock_dir / "backend-dev", "stock", "Stock instruction"),
        (agy_dir / "backend-dev", "agy", "AGY instruction"),
        (project_dir / ".agents" / "skills" / "backend-dev", "project", "Project instruction"),
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
```

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=backend pytest backend/tests/test_agy_skill_sync.py -v`
Expected: FAIL (agy_skills_dir argument not supported or precedence not implemented).

- [ ] **Step 3: Implement AGY scanning and precedence in `SkillManager`**
Update `backend/app/services/skill_manager.py` to:
1. Accept `agy_skills_dir` (defaulting to `os.path.expanduser("~/.gemini/config/skills")`).
2. Update `get_skill()` order:
   - 1. Check Project Local (`.agents/skills/<name>/SKILL.md`) -> tier `project`
   - 2. Check AGY Directory (`<agy_skills_dir>/<name>/SKILL.md`) -> tier `agy`
   - 3. Check Stock Skills Directory (`<stock_skills_dir>/<name>/SKILL.md`) -> tier `stock`
   - 4. Fallback in-memory general skill
3. Update `list_available_skills()` to scan `agy_skills_dir` and tag items with `tier="agy"`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=backend pytest backend/tests/test_agy_skill_sync.py -v`
Expected: PASS (2/2 pass).

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/skill_manager.py backend/tests/test_agy_skill_sync.py
git commit -m "feat(skills): add AGY local skill discovery and precedence in SkillManager"
```

---

### Task 2: Online GitHub & Web URL Skill Downloader Engine

**Files:**
- Modify: `backend/app/services/skill_manager.py`
- Test: `backend/tests/test_skill_downloader.py`

**Interfaces:**
- `SkillManager.normalize_download_url(url: str) -> str`
- `SkillManager.download_online_skill(url: str, skill_name: Optional[str] = None, target: str = "project", project_path: Optional[str] = None) -> SkillInfo`

- [ ] **Step 1: Write the failing test for downloading and sanitizing online skills**

```python
# backend/tests/test_skill_downloader.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.skill_manager import SkillManager

def test_normalize_github_blob_url():
    manager = SkillManager()
    github_blob = "https://github.com/user/repo/blob/main/skills/fastapi/SKILL.md"
    raw_url = manager.normalize_download_url(github_blob)
    assert raw_url == "https://raw.githubusercontent.com/user/repo/main/skills/fastapi/SKILL.md"

def test_download_online_skill(tmp_path):
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
        assert "Expert in async FastAPI" in skill.description
        target_file = project_dir / ".agents" / "skills" / "fastapi-pro" / "SKILL.md"
        assert target_file.exists()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=backend pytest backend/tests/test_skill_downloader.py -v`
Expected: FAIL (methods not defined).

- [ ] **Step 3: Implement `normalize_download_url` and `download_online_skill` in `SkillManager`**
1. Add URL transformation for `github.com/<owner>/<repo>/blob/<branch>/<path>` to `raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`.
2. Use standard `urllib.request.urlopen` with timeout and 512 KB size limit.
3. Validate and parse frontmatter (generate if missing).
4. Save file to either `<project_path>/.agents/skills/<name>/SKILL.md` (if target is "project") or `<stock_skills_dir>/<name>/SKILL.md` (if target is "stock").
5. Return parsed `SkillInfo`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=backend pytest backend/tests/test_skill_downloader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/skill_manager.py backend/tests/test_skill_downloader.py
git commit -m "feat(skills): add online skill downloader and URL sanitizer in SkillManager"
```

---

### Task 3: REST Endpoints for Download, AGY Sync & Role Reassignment

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_skill_sync_routes.py`

**Interfaces:**
- `POST /api/skills/download` (DownloadSkillRequest -> SkillDetail)
- `POST /api/projects/{project_id}/agents/{role}/assign-skill` (AssignSkillRequest -> Agent)

- [ ] **Step 1: Write failing API route test**

```python
# backend/tests/test_skill_sync_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)

def test_get_skills_includes_agy(tmp_path):
    response = client.get("/api/skills")
    assert response.status_code == 200
    skills = response.json()
    assert isinstance(skills, list)
    # Check that skills list has items with tier property
    for s in skills:
        assert "tier" in s
        assert "name" in s

def test_assign_agent_skill(test_db):
    # Project f1 should exist or create one
    client.post("/api/projects", json={"name": "test-sync-p1", "workspace_path": "/tmp/test-sync-p1"})
    
    # Assign a skill to BackendDev
    res = client.post("/api/projects/test-sync-p1/agents/BackendDev/assign-skill", json={
        "skill_name": "systematic-debugger"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "BackendDev"
    assert data["skill_name"] == "systematic-debugger"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=backend pytest backend/tests/test_skill_sync_routes.py -v`
Expected: FAIL with 404 or missing route.

- [ ] **Step 3: Implement DB update and API routes**
1. In `schemas.py`, add `DownloadSkillRequest(url: str, skill_name: Optional[str] = None, target: str = "project", project_id: Optional[str] = None)` and `AssignSkillRequest(skill_name: str)`.
2. In `state_store.py`, add `update_agent_skill(project_id: str, role: str, skill_name: str, skill_tier: str, skill_title: str) -> Optional[Agent]`.
3. In `routes.py`, wire:
   - `POST /api/skills/download`
   - `POST /api/projects/{project_id}/agents/{role}/assign-skill`

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=backend pytest backend/tests/test_skill_sync_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/models/schemas.py backend/app/services/state_store.py backend/app/api/routes.py backend/tests/test_skill_sync_routes.py
git commit -m "feat(api): add endpoints for skill downloading and live role skill assignment"
```

---

### Task 4: Frontend Skill Hub & AGY Sync Modal in Focus Room

**Files:**
- Create: `frontend/src/components/SkillStoreModal.jsx`
- Modify: `frontend/src/components/FocusRoomView.jsx`

**Interfaces:**
- Modal with two tabs:
  1. **Local AGY & Stock Catalogue**: Searchable cards with badges (`AGY`, `Stock`, `Project`), preview button, and "Assign to Agent..." dropdown.
  2. **Online URL Downloader**: Text input for GitHub/Raw URL, target selector (Current Project vs Stock), "Download & Install" button with live status feedback.
- Playbook Header in `FocusRoomView.jsx`: Add "Assign Skill" dropdown directly on the specialist playbook view to swap active skill instantly.

- [ ] **Step 1: Create `SkillStoreModal.jsx`**
Build modern modal with high contrast, responsive tabs, search filter for AGY/Stock skills, and download form.

- [ ] **Step 2: Wire `SkillStoreModal` into `FocusRoomView.jsx`**
Add `[⚡ Skill Hub & AGY Sync]` action button in the Playbooks & Skills toolbar, handle modal state, and refresh skills list on save/assign.

- [ ] **Step 3: Build frontend bundle**
Run: `cd frontend && npm run build`
Expected: Clean build with zero errors.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/SkillStoreModal.jsx frontend/src/components/FocusRoomView.jsx
git commit -m "feat(ui): add Skill Hub modal for AGY browsing and online skill downloading"
```

---

### Task 5: End-to-End Verification & Walkthrough

**Files:**
- Verify: Full pytest suite (`backend/tests/`)
- Verify: Browser interaction testing

- [ ] **Step 1: Run full test suite**
Run: `PYTHONPATH=backend pytest -v backend/tests/`
Expected: 100% tests passing.

- [ ] **Step 2: Restart server and verify live browser UI**
Restart `python3 start_dashboard.py` and inspect `http://127.0.0.1:8000/` with browser subagent.
Verify:
- "Playbooks & Skills" tab has `Skill Hub & AGY Sync` button.
- Modal opens and lists all 22+ AGY skills from `~/.gemini/config/skills/`.
- Assigning an AGY skill (e.g. `test-driven-development`) updates the agent live.

- [ ] **Step 3: Update walkthrough artifact and git commit**
Update `walkthrough.md` with verification results.
