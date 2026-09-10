# Project Tech Lead Agent & Deep Workspace Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 8th agent `TechLead` (Project Lead & Chief Reporter) along with a Deep Workspace Inspector (README parsing, directory topology, test command detection) and an interactive Daily Standup Briefing UI for the Virtual AI Office PM Dashboard.

**Architecture:** The `WorkspaceInspector` deepens analysis to build a comprehensive Project Intelligence Profile (README, folder structure, test commands, Docker), persisted in SQLite `StateStore`. `AgentRunner` injects this profile into all agent prompts. A new `TechLeadService` synthesizes real-time standup reports and powers conversational Q&A for the PM. The React frontend presents a prominent Tech Lead desk card, daily standup button, and an interactive 4-section briefing modal.

**Tech Stack:** Python 3.10+, FastAPI, SQLite, Pydantic, pytest, React 18, Vite, Lucide-React, Vanilla CSS.

## Global Constraints

- Never break existing 9 backend tests in `tests/`.
- Maintain SQLite database backward compatibility using safe `ALTER TABLE` migrations.
- Respect guardrail security: truncate README content to 3,000 characters and ignore system folders.
- Follow Linear/Vercel clean design aesthetic with rich micro-animations.

---

### Task 1: Deep Workspace Inspector (README, Directory Topology, Test Commands)

**Files:**
- Modify: `backend/app/services/workspace_inspector.py`
- Test: `backend/tests/test_deep_workspace_inspector.py`

**Interfaces:**
- Produces: `WorkspaceInspector._inspect_codebase(path) -> Dict[str, Any]` returning enriched metadata dictionary including `purpose_summary`, `directory_structure`, `test_command`, `has_docker`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_deep_workspace_inspector.py
import os
import tempfile
import pytest
from app.services.workspace_inspector import WorkspaceInspector

def test_deep_inspection_readme_and_topology():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock project structure
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# E-Commerce Storefront\nA modern online shopping platform with Stripe checkout.")
            
        os.makedirs(os.path.join(tmpdir, "src", "components"))
        os.makedirs(os.path.join(tmpdir, "src", "api"))
        os.makedirs(os.path.join(tmpdir, "tests"))
        
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            f.write('{"name": "ecommerce-app", "scripts": {"test": "vitest run"}, "dependencies": {"react": "^18.0.0"}}')
            
        inspector = WorkspaceInspector()
        valid, msg, meta = inspector.validate_guardrails(tmpdir)
        
        assert valid is True
        assert "purpose_summary" in meta
        assert "E-Commerce Storefront" in meta["purpose_summary"]
        assert meta["test_command"] == "vitest run"
        assert any("src/components" in d for d in meta["directory_structure"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_deep_workspace_inspector.py -v`  
Expected: FAIL with missing keys `purpose_summary` and `directory_structure`.

- [ ] **Step 3: Implement deep inspection logic**

In `backend/app/services/workspace_inspector.py`:
- In `_inspect_codebase(path)`:
  - Check for `README.md` (or `readme.md`, `README.txt`), extract first 3000 chars, parse first `# Title` or first paragraph into `purpose_summary`.
  - Scan directory tree up to depth 2, recording significant directories (`src/`, `api/`, `components/`, `models/`, `controllers/`, `tests/`, `routes/`).
  - Read `package.json` `scripts.test` if present, assign to `meta["test_command"]`.
  - Check for `Dockerfile` or `docker-compose.yml`, assign `meta["has_docker"] = True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_deep_workspace_inspector.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/workspace_inspector.py backend/tests/test_deep_workspace_inspector.py
git commit -m "feat(inspector): add README parsing, directory topology, and test command detection"
```

---

### Task 2: State Store Project Metadata & TechLead Roster Tailoring

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/services/project_manager.py`
- Test: `backend/tests/test_state_store_tech_lead.py`

**Interfaces:**
- Consumes: `AgentRole.TECH_LEAD = "TechLead"`
- Produces: `StateStore.get_project_metadata(project_id) -> Dict[str, Any]`
- Produces: `WorkspaceInspector.generate_tailored_roster()` includes `TechLead` as the first agent.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_state_store_tech_lead.py
import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.models.schemas import AgentRole

def test_project_metadata_persistence_and_tech_lead():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = StateStore(db_path=db_path)
        pm = ProjectManager(store=store)
        
        # Create workspace with requirements.txt
        ws_dir = os.path.join(tmpdir, "ws")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "requirements.txt"), "w") as f:
            f.write("fastapi\npytest\n")
            
        proj = pm.register_project("proj-test", "Test Proj", ws_dir)
        
        # Check metadata stored
        meta = store.get_project_metadata("proj-test")
        assert meta is not None
        assert "Python" in meta.get("stack_type", "")
        
        # Check TechLead agent registered
        agents = store.list_agents("proj-test")
        roles = [a.role for a in agents]
        assert "TechLead" in roles
        assert len(agents) == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_state_store_tech_lead.py -v`  
Expected: FAIL with missing method `get_project_metadata` or missing `TechLead` in roles.

- [ ] **Step 3: Implement schemas, state store migration, and roster update**

- Add `TECH_LEAD = "TechLead"` to `AgentRole` enum in `backend/app/models/schemas.py`.
- In `backend/app/services/state_store.py`:
  - Run `ALTER TABLE projects ADD COLUMN metadata_json TEXT DEFAULT '{}'` safely inside a `try/except sqlite3.OperationalError` during `_init_db`.
  - Update `create_project` to accept `metadata: Optional[Dict[str, Any]] = None` and store `json.dumps(metadata)`.
  - Add `get_project_metadata(project_id: str) -> Dict[str, Any]`.
- In `backend/app/services/project_manager.py`:
  - Pass `meta` to `create_project`.
  - Add `TechLead` to `DEFAULT_ROLES`.
  - In `WorkspaceInspector.generate_tailored_roster(meta)`: add `TechLead` as the 1st agent in all rosters (Node.js, Python, Generic).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_state_store_tech_lead.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/services/state_store.py backend/app/services/project_manager.py backend/tests/test_state_store_tech_lead.py
git commit -m "feat(store): persist project metadata and register TechLead role"
```

---

### Task 3: Context-Aware Agent Execution & Runner Prompt Injection

**Files:**
- Modify: `backend/app/services/agent_runner.py`
- Modify: `backend/app/services/orchestrator.py`
- Test: `backend/tests/test_context_aware_runner.py`

**Interfaces:**
- Consumes: `meta = store.get_project_metadata(project_id)`
- Produces: `runner.dispatch_agent_task(..., project_context=meta)` injects project intelligence into agent system instruction.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_context_aware_runner.py
import pytest
from app.services.agent_runner import AgentRunner

@pytest.mark.asyncio
async def test_context_aware_system_instructions():
    runner = AgentRunner(use_mock=True)
    events = []
    async def callback(event_type, data):
        events.append((event_type, data))
        
    context = {
        "suggested_name": "Payment Gateway",
        "purpose_summary": "Handles credit card processing and billing webhooks.",
        "stack_type": "Python / FastAPI",
        "frameworks": ["fastapi", "stripe"],
        "test_runner": "pytest",
        "test_command": "pytest tests/ -v"
    }
    
    res = await runner.dispatch_agent_task(
        project_id="p1",
        role="BackendDev",
        prompt="Implement stripe webhook verification",
        workspace_path="/mock/path",
        project_context=context,
        event_callback=callback
    )
    assert res["status"] == "SUCCESS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_context_aware_runner.py -v`  
Expected: FAIL if `project_context` unexpected argument.

- [ ] **Step 3: Implement context injection in AgentRunner & Orchestrator**

- In `backend/app/services/agent_runner.py`:
  - Add `project_context: Optional[Dict[str, Any]] = None` to `dispatch_agent_task`.
  - Build enriched `system_instructions`:
    ```python
    if project_context:
        ctx_header = (
            f"Project: {project_context.get('suggested_name', project_id)}\n"
            f"Purpose: {project_context.get('purpose_summary', 'Software project')}\n"
            f"Stack: {project_context.get('stack_type', 'Generic')} (Frameworks: {', '.join(project_context.get('frameworks', []))})\n"
            f"Test Suite: {project_context.get('test_runner', 'automated')} (Command: {project_context.get('test_command', 'run tests')})\n"
        )
    ```
- In `backend/app/services/orchestrator.py`:
  - Retrieve `meta = self.store.get_project_metadata(project_id)` at start of `execute_pm_directive` and pass `project_context=meta` to all `runner.dispatch_agent_task` calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_context_aware_runner.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_runner.py backend/app/services/orchestrator.py backend/tests/test_context_aware_runner.py
git commit -m "feat(runner): inject deep project intelligence into agent system instructions"
```

---

### Task 4: Tech Lead Standup Service & API Endpoints

**Files:**
- Create: `backend/app/services/tech_lead_service.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_tech_lead_service.py`

**Interfaces:**
- Produces: `TechLeadService.generate_standup(project_id) -> Dict[str, Any]`
- Produces: `TechLeadService.chat_with_lead(project_id, message) -> Dict[str, Any]`
- Endpoints: `POST /api/projects/{project_id}/standup`, `POST /api/projects/{project_id}/lead/chat`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_tech_lead_service.py
import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.tech_lead_service import TechLeadService

def test_tech_lead_standup_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=os.path.join(tmpdir, "test.db"))
        pm = ProjectManager(store=store)
        ws_dir = os.path.join(tmpdir, "ws")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "package.json"), "w") as f:
            f.write('{"name": "demo-app"}')
            
        pm.register_project("demo", "Demo App", ws_dir)
        
        # Add sample tasks
        store.create_task("t1", "demo", "Design API", "Spec schema", "Architect")
        store.update_task_status("t1", "DONE")
        store.create_task("t2", "demo", "Write Endpoints", "FastAPI routes", "BackendDev")
        store.update_task_status("t2", "IN_PROGRESS")
        
        service = TechLeadService(store=store, pm=pm)
        standup = service.generate_standup("demo")
        
        assert standup["project_id"] == "demo"
        assert standup["health_status"] in ["ON_TRACK", "AT_RISK", "BLOCKED"]
        assert standup["progress_percent"] == 50
        assert len(standup["completed_items"]) == 1
        assert len(standup["active_items"]) == 1
        assert "Demo App" in standup["summary"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tech_lead_service.py -v`  
Expected: FAIL with module `app.services.tech_lead_service` not found.

- [ ] **Step 3: Implement TechLeadService and API routes**

- Create `backend/app/services/tech_lead_service.py`:
  - `generate_standup(project_id)`: gathers tasks, agent states, project metadata. Computes progress % (`done / total * 100`). Identifies blockers (BLOCKED agents or FAILED tasks). Synthesizes executive summary.
  - `chat_with_lead(project_id, message)`: answers PM queries using project metadata, task history, and current status.
- In `backend/app/api/routes.py`:
  - Wire `POST /api/projects/{project_id}/standup`
  - Wire `POST /api/projects/{project_id}/lead/chat`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_tech_lead_service.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tech_lead_service.py backend/app/api/routes.py backend/tests/test_tech_lead_service.py
git commit -m "feat(lead): implement TechLeadService and standup briefing endpoints"
```

---

### Task 5: Frontend UI: Tech Lead Desk Card & Standup Modal

**Files:**
- Create: `frontend/src/components/TechLeadCard.jsx`
- Create: `frontend/src/components/TechLeadStandupModal.jsx`
- Modify: `frontend/src/components/OfficeFloorView.jsx`
- Modify: `frontend/src/components/DualSplitView.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Renders: Featured Tech Lead desk card on Office Floor View with `👑 Tech Lead` crown badge and `[ 🎙️ Standup Briefing ]` button.
- Renders: Standup Modal showing 4 sections (Completed, In Progress, Blockers, Next Steps) + progress percentage + interactive Tech Lead chat.
- Renders: Mini Tech Lead status pill in Dual Split View column header.

- [ ] **Step 1: Create TechLeadStandupModal.jsx**

Build modal component with:
- Header: Project name, Health badge (🟢 On Track, 🟡 At Risk, 🔴 Blocked), Progress bar (0-100%).
- 4-Card layout:
  - 🟢 Completed Tasks
  - 🔵 Active / In-Progress
  - 🔴 Blockers & Attention Needed
  - 🟣 Next Priorities
- Executive summary generated by Tech Lead.
- Bottom interactive Q&A bar: PM types question -> hits `/api/projects/{project_id}/lead/chat` -> displays reply.

- [ ] **Step 2: Create TechLeadCard.jsx & Integrate into OfficeFloorView**

- Create `TechLeadCard.jsx` with distinct styling: wider card, gold border accent, glowing crown icon, live status badge, and `[ 🎙️ Standup Briefing ]` button.
- In `OfficeFloorView.jsx`: Separate the `TechLead` agent from the sub-agents grid, rendering the `TechLeadCard` at the top of the floor view.
- In `DualSplitView.jsx`: Add a mini `👑 Tech Lead: [Status]` button in each column header to open the Standup modal for that project.

- [ ] **Step 3: Add CSS styling in index.css**

- Add `.tech-lead-card`, `.crown-badge`, `.standup-modal`, `.standup-grid`, `.health-pill`, `.progress-track` styles matching the dark/light SaaS theme.

- [ ] **Step 4: Build frontend bundle and verify no compile errors**

Run: `cd frontend && npx vite build`  
Expected: `built in ...ms` without errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TechLeadCard.jsx frontend/src/components/TechLeadStandupModal.jsx frontend/src/components/OfficeFloorView.jsx frontend/src/components/DualSplitView.jsx frontend/src/App.jsx frontend/src/index.css
git commit -m "feat(ui): add Tech Lead desk card, daily standup button, and briefing modal"
```

---

### Task 6: Verification, End-to-End Testing & Walkthrough

**Files:**
- Update: `task.md`
- Update: `walkthrough.md`

- [ ] **Step 1: Run complete backend pytest test suite**

Run: `cd backend && python -m pytest tests/ -v`  
Expected: All tests pass (including existing 9 tests + all new tests).

- [ ] **Step 2: Test live browser experience with browser_subagent**

- Restart dashboard server.
- Verify Office Floor View renders the Tech Lead desk card with crown badge.
- Click `[ 🎙️ Standup Briefing ]` and confirm modal loads synthesized standup report and chat works.
- Check Dual Split View column header.
- Take screenshots and record walkthrough artifact.

- [ ] **Step 3: Commit all changes**

```bash
git add .
git commit -m "feat: complete Project Tech Lead agent and Deep Workspace Inspector"
```
