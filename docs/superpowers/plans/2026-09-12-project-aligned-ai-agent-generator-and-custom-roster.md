# Project-Aligned AI Agent Generator & Custom Roster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an AI-powered team generation engine that inspects a workspace and dynamically creates specialized agent roles tailored to that codebase, along with a UI for human PMs to add, remove, and regenerate agents.

**Architecture:** 
1. Backend: Extend `StateStore` with agent addition/deletion and add Pydantic schemas. 
2. Engine: Implement `auto_generate_tailored_roster` in `TechLeadService`/`WorkspaceInspector` with LLM prompt via `agy` and heuristic fallback.
3. Runner: Enhance `AgentRunner` to dynamically bind custom agent descriptions as system personas.
4. API: Expose `/agents/auto-generate`, `POST /agents`, and `DELETE /agents/{role}`.
5. Frontend: Add `AddAgentModal`, `AutoGenerateTeamModal`, "+ Add Specialist" card, and "⚡ AI Team" header action in `OfficeFloorView.jsx`.

**Tech Stack:** FastAPI, Python Pydantic, SQLite, React (Vite), Vanilla CSS tokens.

## Global Constraints
- Preserve Vanilla CSS design tokens (no runtime Tailwind dependency).
- Protect `TechLead` from deletion (always preserved as the project lead).
- Keep all 85 existing backend tests passing without regressions.
- Ensure cross-platform Windows compatibility (`cmd.exe` / `powershell`).

---

### Task 1: Backend Data Models & StateStore Methods

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/state_store.py`
- Test: `backend/tests/test_custom_agents.py`

**Interfaces:**
- Consumes: `StateStore` SQLite connection
- Produces: `StateStore.delete_agent(project_id, role) -> bool`, `StateStore.add_agent(project_id, role, title, description, skill_name, skill_tier) -> AgentState`

- [ ] **Step 1: Write the failing tests for StateStore agent methods**
```python
import pytest
from app.services.state_store import StateStore
from app.models.schemas import AgentStatus

def test_add_and_delete_custom_agent(tmp_path):
    db_file = str(tmp_path / "test_state.db")
    store = StateStore(db_path=db_file)
    store.create_project("proj-1", "Test App", "/test/path")
    
    # Add custom agent
    agent = store.add_agent(
        project_id="proj-1",
        role="GamePhysicsDev",
        title="Physics & Vehicle Dynamics Engineer",
        description="Simulates aerodynamic forces and tire grip.",
        skill_name="systematic-debugger",
        skill_tier="stock"
    )
    assert agent.role == "GamePhysicsDev"
    assert agent.skill_title == "Physics & Vehicle Dynamics Engineer"
    assert "aerodynamic forces" in agent.thought
    
    # Retrieve
    agents = store.get_all_agent_states("proj-1")
    assert any(a.role == "GamePhysicsDev" for a in agents)
    
    # Delete custom agent
    deleted = store.delete_agent("proj-1", "GamePhysicsDev")
    assert deleted is True
    assert not any(a.role == "GamePhysicsDev" for a in store.get_all_agent_states("proj-1"))
    
    # TechLead cannot be deleted
    store.set_agent_status("proj-1", "TechLead", "IDLE")
    cannot_delete = store.delete_agent("proj-1", "TechLead")
    assert cannot_delete is False
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_add_and_delete_custom_agent -v`
Expected: FAIL with `AttributeError: 'StateStore' object has no attribute 'add_agent'`

- [ ] **Step 3: Implement schemas and StateStore methods**
In `backend/app/models/schemas.py`:
Add `CustomAgentCreateRequest`:
```python
class CustomAgentCreateRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=50)
    title: str = Field(..., min_length=2, max_length=80)
    description: str = Field(..., min_length=5, max_length=300)
    skill_name: Optional[str] = None
    skill_tier: Optional[str] = "stock"

class AutoGenerateRosterRequest(BaseModel):
    replace_existing: bool = True
```
In `backend/app/services/state_store.py`:
Implement `add_agent` and `delete_agent`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_add_and_delete_custom_agent -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/models/schemas.py backend/app/services/state_store.py backend/tests/test_custom_agents.py
git commit -m "feat: add custom agent schema and StateStore methods"
```

---

### Task 2: AI Team Generation Engine

**Files:**
- Modify: `backend/app/services/workspace_inspector.py`
- Modify: `backend/app/services/tech_lead_service.py`
- Test: `backend/tests/test_custom_agents.py`

**Interfaces:**
- Consumes: `ProjectMetadata`, `TechLeadService`, `WorkspaceInspector`
- Produces: `TechLeadService.auto_generate_roster(project_id: str, replace_existing: bool = True) -> Dict[str, Any]`

- [ ] **Step 1: Write the failing tests for auto-generating roster**
```python
def test_auto_generate_roster_heuristics(tmp_path):
    from app.services.tech_lead_service import TechLeadService
    from app.services.project_manager import ProjectManager
    from app.services.state_store import StateStore
    
    db_file = str(tmp_path / "test_state.db")
    store = StateStore(db_path=db_file)
    pm = ProjectManager(store=store)
    tls = TechLeadService(store=store, pm=pm)
    
    # Create project with 3D game metadata
    meta = {
        "path": "/test/f1-game",
        "suggested_name": "F1 3D Simulation",
        "stack_type": "3D WebGL (Three.js + Vite)",
        "frameworks": ["three", "vite"],
        "purpose_summary": "Formula 1 Racing Game simulation with aerodynamic physics and tracks."
    }
    store.create_project("proj-game", "F1 3D Simulation", "/test/f1-game", metadata=meta)
    store.set_agent_status("proj-game", "TechLead", "IDLE")
    
    result = tls.auto_generate_roster("proj-game", replace_existing=True)
    assert result["status"] == "SUCCESS"
    agents = result["agents"]
    roles = [a["role"] for a in agents]
    assert "TechLead" in roles
    # Verify specialized roles generated
    assert any("Physics" in a["title"] or "Three" in a["title"] or "Game" in a["title"] for a in agents)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_auto_generate_roster_heuristics -v`
Expected: FAIL with `AttributeError: 'TechLeadService' object has no attribute 'auto_generate_roster'`

- [ ] **Step 3: Implement `auto_generate_roster` in `TechLeadService`**
In `backend/app/services/tech_lead_service.py`:
Implement `auto_generate_roster(self, project_id: str, replace_existing: bool = True)`:
1. Gather metadata (`store.get_project_metadata(project_id)`).
2. If `has_agy` CLI is present and not testing: prompt `agy` for 3-5 specialized sub-agents.
3. Fallback: use domain heuristics (detect 3D/Three.js, ML, FastAPI, React/Next, etc.) to generate 3-5 tailored roles.
4. Save to `StateStore`. If `replace_existing`, remove old sub-agents except `TechLead`, then add new agents.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_auto_generate_roster_heuristics -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/tech_lead_service.py backend/tests/test_custom_agents.py
git commit -m "feat: implement AI and heuristic team generation engine"
```

---

### Task 3: Dynamic Persona Execution in `AgentRunner`

**Files:**
- Modify: `backend/app/services/agent_runner.py`
- Test: `backend/tests/test_custom_agents.py`

**Interfaces:**
- Consumes: Custom roles from `StateStore.get_agent_status(project_id, role)`
- Produces: Dispatches tasks with persona generated from `agent.thought` / `agent.skill_title`

- [ ] **Step 1: Write the failing test for dynamic role persona in `AgentRunner`**
```python
@pytest.mark.asyncio
async def test_agent_runner_custom_role_persona(tmp_path):
    from app.services.agent_runner import AgentRunner
    from app.services.state_store import StateStore
    
    db_file = str(tmp_path / "test_state.db")
    store = StateStore(db_path=db_file)
    store.create_project("proj-c", "Custom App", "/test/custom")
    store.add_agent(
        "proj-c",
        role="CryptoAuditor",
        title="Smart Contract Security Auditor",
        description="Audits EVM bytecode and gas usage."
    )
    
    runner = AgentRunner(use_mock=True, store=store)
    events = []
    async def cb(ev, data):
        events.append((ev, data))
        
    res = await runner.dispatch_agent_task(
        project_id="proj-c",
        role="CryptoAuditor",
        prompt="Audit the staking contract for reentrancy bugs.",
        workspace_path="/test/custom",
        event_callback=cb
    )
    assert res["role"] == "CryptoAuditor"
    assert res["status"] == "SUCCESS"
    # Verify persona was reflected in events
    deltas = [d.get("thought", "") for ev, d in events if ev == "AGENT_THOUGHT_DELTA"]
    assert any("CryptoAuditor" in d or "Smart Contract" in d or "EVM" in d for d in deltas)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_agent_runner_custom_role_persona -v`

- [ ] **Step 3: Update `AgentRunner` to bind custom personas**
In `backend/app/services/agent_runner.py`:
When `role` is not in `ROLE_PROMPTS`, retrieve `agent_state.thought` or `agent_state.skill_title` from `self.store` and inject it into the instructions and simulation stream.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_agent_runner_custom_role_persona -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/agent_runner.py backend/tests/test_custom_agents.py
git commit -m "feat: support dynamic custom role personas in AgentRunner"
```

---

### Task 4: API Endpoints in `routes.py`

**Files:**
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_custom_agents.py`

**Interfaces:**
- `POST /api/projects/{project_id}/agents/auto-generate`
- `POST /api/projects/{project_id}/agents`
- `DELETE /api/projects/{project_id}/agents/{role}`

- [ ] **Step 1: Write the failing API integration tests**
```python
def test_custom_agent_api_endpoints(client, tmp_path):
    # Register project
    res = client.post("/api/projects", json={
        "project_id": "api-proj",
        "name": "API Proj",
        "workspace_path": str(tmp_path)
    })
    assert res.status_code == 200
    
    # 1. Add custom agent
    res = client.post("/api/projects/api-proj/agents", json={
        "role": "PerformanceAuditor",
        "title": "Latency & Core Web Vitals Specialist",
        "description": "Profiles memory consumption and render bottleneck.",
        "skill_name": "performance-optimization"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "PerformanceAuditor"
    
    # 2. Delete custom agent
    del_res = client.delete("/api/projects/api-proj/agents/PerformanceAuditor")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "DELETED"
    
    # 3. Cannot delete TechLead
    del_tl = client.delete("/api/projects/api-proj/agents/TechLead")
    assert del_tl.status_code == 400
    
    # 4. Auto-generate team
    gen_res = client.post("/api/projects/api-proj/agents/auto-generate", json={"replace_existing": True})
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert len(gen_data["agents"]) >= 3
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_custom_agent_api_endpoints -v`
Expected: FAIL 404 on endpoint

- [ ] **Step 3: Implement endpoints in `backend/app/api/routes.py`**
Wire up `POST /api/projects/{project_id}/agents/auto-generate`, `POST /api/projects/{project_id}/agents`, and `DELETE /api/projects/{project_id}/agents/{role}` with WebSocket event broadcasts (`AGENT_ROSTER_UPDATED`, `AGENT_STATE_UPDATE`, `AGENT_DELETED`).

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest backend/tests/test_custom_agents.py::test_custom_agent_api_endpoints -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/api/routes.py backend/tests/test_custom_agents.py
git commit -m "feat: expose custom agent management and auto-generate endpoints"
```

---

### Task 5: Frontend UI - Add Agent Modal & Auto-Generate Modal

**Files:**
- Create: `frontend/src/components/AddAgentModal.jsx`
- Create: `frontend/src/components/AutoGenerateTeamModal.jsx`

**Interfaces:**
- Consumes: Available skills from `/api/skills`, project metadata
- Produces: `onAddAgent({ role, title, description, skill_name })`, `onApplyTeam(roster)`

- [ ] **Step 1: Create `AddAgentModal.jsx`**
Clean modal with inputs for:
- Role Identifier (alphanumeric, e.g. `GameDev`)
- Title (e.g. `Physics Simulation Specialist`)
- Description / Responsibility
- Initial Playbook / Skill dropdown
- Cancel & Create buttons

- [ ] **Step 2: Create `AutoGenerateTeamModal.jsx`**
Modal displaying:
- Project analysis header (Stack, Purpose)
- Loading state while AI synthesizes team
- Preview list of proposed agents (Roles, Titles, Descriptions, Recommended Skills)
- "Apply AI Team to Project" button (calls `/api/projects/{project_id}/agents/auto-generate`)

- [ ] **Step 3: Commit**
```bash
git add frontend/src/components/AddAgentModal.jsx frontend/src/components/AutoGenerateTeamModal.jsx
git commit -m "feat: create AddAgentModal and AutoGenerateTeamModal components"
```

---

### Task 6: Frontend UI - Office Floor View Integration & Styling

**Files:**
- Modify: `frontend/src/components/OfficeFloorView.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `AddAgentModal`, `AutoGenerateTeamModal`
- Produces: Office room header "⚡ AI Team" button, "+ Add Specialist" card in `agent-desks-grid`, delete agent button.

- [ ] **Step 1: Update `OfficeFloorView.jsx`**
- Add "⚡ AI Team" button in `.room-header` actions.
- Add "+ Add Specialist" desk card at the end of `agent-desks-grid`.
- Add delete button `✕` on hover for non-TechLead agents with confirm dialog.
- Enhance `ROLE_ICONS` fallback so custom roles receive a clean default icon (e.g. `Bot`, `Sparkles`, or `Cpu`).

- [ ] **Step 2: Update `App.jsx`**
- Wire up state for `isAddAgentOpen`, `isAutoGenOpen`, and connect API calls to refresh `agentStates`.
- Handle WebSocket event `AGENT_ROSTER_UPDATED` to refresh project agents automatically.

- [ ] **Step 3: Update `index.css`**
- Add styles for `.add-specialist-card`, `.auto-generate-team-modal`, `.agent-delete-btn`, and team preview list cards.

- [ ] **Step 4: Verify frontend build**
Run: `npm.cmd run build` in `frontend/`
Expected: Success with 0 errors.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/OfficeFloorView.jsx frontend/src/App.jsx frontend/src/index.css
git commit -m "feat: integrate AI team generator and custom agent controls into OfficeFloorView"
```

---

### Task 7: End-to-End Verification

**Files:**
- Entire codebase

- [ ] **Step 1: Run full backend test suite**
Run: `python -m pytest backend/tests/ -v`
Expected: 100% tests pass (all existing 85 tests + new tests).

- [ ] **Step 2: Run frontend production build**
Run: `npm.cmd run build` in `frontend/`
Expected: Successful build with 0 warnings/errors.

- [ ] **Step 3: Verify running dashboard**
Verify responsiveness on `http://127.0.0.1:8000`.
