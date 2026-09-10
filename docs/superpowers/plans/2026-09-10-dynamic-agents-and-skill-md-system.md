# Dynamic Agent & SKILL.md Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the fixed 8-role agent preset into a Dynamic AI Team Composition powered by a Hybrid `SKILL.md` system (80% Curated Stock Playbooks + 20% Injected Project Context), with dynamic roster tailoring, editable playbooks, and flexible UI visualization.

**Architecture:** A `SkillManager` service discovers, caches, and loads markdown-based `SKILL.md` playbooks from a built-in Stock library (`backend/skills/`) and project-local overrides (`.agents/skills/`). The `WorkspaceInspector` analyzes project dependencies, topology, and README to synthesize a tailored agent team (3–6 agents) mapped to matching skills. `AgentRunner` injects the parsed playbook + project context at runtime, while the frontend provides dynamic office floor desks and a live Skill Playbook viewer/editor.

**Tech Stack:** FastAPI, Python 3.10+, Pydantic v2, Pytest, React 18, Vite, Lucide Icons, Markdown / Frontmatter parsing.

---

## Global Constraints
- Preserve backward compatibility with existing projects and default standard roles (`TechLead`, `Backend`, `Frontend`, etc.).
- All existing 16 unit tests must continue passing.
- New features must be thoroughly test-driven with unit and integration tests.
- Support both Light and Dark modes seamlessly with solid contrast.

---

## Proposed Changes

### Backend Services & Models

#### [NEW] `backend/app/services/skill_manager.py`
- Discovers and loads `SKILL.md` files from `backend/skills/` (Stock) and `<project_path>/.agents/skills/` (Project Custom).
- Parses YAML frontmatter (`name`, `title`, `description`, `tools`, `triggers`, `tier`).
- Synthesizes the full agent prompt: `[Role Identity] + [SKILL.md Playbook (80%)] + [Project Context (20%)]`.
- Provides CRUD capabilities for custom project skills.

#### [NEW] `backend/skills/` (Curated Stock Library)
- `tech-lead/SKILL.md`
- `architect/SKILL.md`
- `backend-dev/SKILL.md`
- `frontend-dev/SKILL.md`
- `qa-engineer/SKILL.md`
- `devops-engineer/SKILL.md`
- `security-auditor/SKILL.md`
- `systematic-debugger/SKILL.md`
- `ml-data-engineer/SKILL.md`

#### [MODIFY] `backend/app/models/schemas.py`
- Change `AgentRole` from a restrictive enum to allow dynamic custom roles (`role: str`), while maintaining constants for standard roles.
- Add `skill_name: Optional[str]` and `skill_tier: Optional[str]` ("stock" | "custom") to `Agent` schema.
- Add `SkillMetadata` and `SkillDetail` schemas.

#### [MODIFY] `backend/app/services/workspace_inspector.py`
- Implement dynamic team composition recommendation: inspects tech stack (Python/FastAPI, Node/React, PyTorch/ML, Go, Rust, etc.) and recommends a tailored 3–6 agent roster.
- Assigns corresponding `SKILL.md` to each agent.

#### [MODIFY] `backend/app/services/agent_runner.py`
- Replace static `ROLE_PROMPTS` dictionary lookup with dynamic `SkillManager.get_agent_system_prompt()`.

#### [MODIFY] `backend/app/api/routes.py`
- Add endpoints:
  - `GET /api/skills` — List all available stock and custom skills.
  - `GET /api/projects/{id}/skills` — List assigned skills for a project's team.
  - `GET /api/projects/{id}/skills/{role}` — Retrieve raw `SKILL.md` for an agent.
  - `PUT /api/projects/{id}/skills/{role}` — Update / customize `SKILL.md` content for an agent.
  - `POST /api/projects/{id}/skills/synthesize` — Ask Tech Lead to generate a custom skill for an emerging stack.

---

### Frontend UI

#### [MODIFY] `frontend/src/components/OfficeFloorView.jsx` & `DualSplitView.jsx`
- Support dynamic roster lengths (e.g. 3, 4, 5, or 8 desks) with responsive layout and dynamic avatar styling.
- Display skill badges on agent desks.

#### [NEW] `frontend/src/components/SkillPlaybookModal.jsx` (or Focus Room Tab)
- Tab in Focus Room to view the active `SKILL.md` of the selected agent.
- High-contrast Markdown renderer with edit mode for PM to modify rules and workflow live.

---

## Execution Tasks

### Task 1: SkillManager Service & Stock Playbooks
**Files:**
- Create: `backend/app/services/skill_manager.py`
- Create: `backend/skills/tech-lead/SKILL.md`
- Create: `backend/skills/backend-dev/SKILL.md`
- Create: `backend/skills/frontend-dev/SKILL.md`
- Create: `backend/skills/qa-engineer/SKILL.md`
- Create: `backend/skills/devops-engineer/SKILL.md`
- Create: `backend/skills/security-auditor/SKILL.md`
- Create: `backend/skills/systematic-debugger/SKILL.md`
- Create: `backend/skills/ml-data-engineer/SKILL.md`
- Test: `backend/tests/test_skill_manager.py`

- [ ] **Step 1: Write unit tests for SkillManager**
  - Test loading stock skill by role name
  - Test frontmatter parsing (name, description, tools)
  - Test project-local skill override (`.agents/skills/<role>/SKILL.md`)
  - Test prompt synthesis combining Stock playbook + Project Context
- [ ] **Step 2: Implement Stock SKILL.md files**
  - High quality markdown playbooks with workflow, guidelines, constraints
- [ ] **Step 3: Implement `SkillManager` class**
  - Discovery, caching, frontmatter parsing, prompt generation
- [ ] **Step 4: Run tests to verify pass**
  - `PYTHONPATH=backend pytest -v backend/tests/test_skill_manager.py`

---

### Task 2: Dynamic Schema & Context-Aware AgentRunner Integration
**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/agent_runner.py`
- Test: `backend/tests/test_dynamic_agent_runner.py`

- [ ] **Step 1: Write unit tests for dynamic roles and SkillManager integration in AgentRunner**
- [ ] **Step 2: Update `schemas.py` to allow flexible role strings and skill metadata**
- [ ] **Step 3: Connect `SkillManager` into `AgentRunner.run_agent()`**
- [ ] **Step 4: Verify all existing tests pass (`pytest backend/tests/`)**

---

### Task 3: Dynamic Roster Generation in WorkspaceInspector
**Files:**
- Modify: `backend/app/services/workspace_inspector.py`
- Modify: `backend/app/services/project_manager.py`
- Test: `backend/tests/test_dynamic_roster_generation.py`

- [ ] **Step 1: Write test for stack-tailored roster generation**
  - e.g. React project -> Frontend, Backend, QA, TechLead (4 agents)
  - e.g. Python ML project -> MLDataEngineer, Backend, QA, TechLead
- [ ] **Step 2: Implement `generate_tailored_roster()` with stack heuristics and skill assignments**
- [ ] **Step 3: Run tests to verify pass**

---

### Task 4: Skill Management Endpoints
**Files:**
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_skill_routes.py`

- [ ] **Step 1: Write tests for `GET /api/skills`, `GET /api/projects/{id}/skills/{role}`, `PUT /api/projects/{id}/skills/{role}`**
- [ ] **Step 2: Implement endpoints in `routes.py`**
- [ ] **Step 3: Verify with pytest**

---

### Task 5: Frontend Dynamic Office Floor & Skill Playbook Viewer
**Files:**
- Create: `frontend/src/components/SkillPlaybookModal.jsx`
- Modify: `frontend/src/components/FocusRoomView.jsx` (Add Playbook / Skill tab)
- Modify: `frontend/src/components/OfficeFloorView.jsx` (Dynamic agent grid)
- Modify: `frontend/src/index.css` (Styling for playbook editor and dynamic cards)

- [ ] **Step 1: Add Playbook tab in Focus Room with Markdown viewer and Edit mode**
- [ ] **Step 2: Adapt Office Floor grid for dynamic team sizes (3–8 agents)**
- [ ] **Step 3: Build frontend bundle with `npm run build`**
- [ ] **Step 4: Manual verification on `http://127.0.0.1:8000/`**

---

## Verification Plan

### Automated Tests
- `PYTHONPATH=backend pytest -v backend/tests/` (all 16 existing + new tests passing)

### Manual Verification
- Open Dashboard in browser (`http://127.0.0.1:8000/`)
- Inspect a project: see tailored dynamic team on the office floor
- Open Focus Room: click "Playbook" tab to view agent's `SKILL.md`
- Edit a rule in the playbook, save, and verify it updates in the backend
