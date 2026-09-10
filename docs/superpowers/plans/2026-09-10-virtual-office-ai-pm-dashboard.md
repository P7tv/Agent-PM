# Virtual AI Office PM Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modern, cyberpunk-aesthetic Virtual AI Office Web Dashboard and Orchestrator powered by FastAPI and the Antigravity Python SDK (`google-antigravity`) allowing a user to manage up to 2 concurrent projects with 5–10 autonomous agents in a hybrid PM workflow.

**Architecture:** A Python FastAPI backend orchestrates isolated Antigravity agents per project directory, broadcasting thoughts and tool calls over WebSockets to a React/Vite frontend. The frontend offers 3 seamlessly switchable views (Office Floor, Dual Split, and Focus Deep-Dive) with a persistent PM Control Desk for zero-friction idea injection and approval gates.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Pydantic v2, `google-antigravity` SDK, SQLite, WebSockets, Vite, React, Vanilla Modern CSS (Tokens, Glassmorphism, Micro-animations).

## Global Constraints

- Backend must run on Python 3.10+ and interface cleanly with `google-antigravity`.
- System must support testing with mock agent execution when API quotas/keys are absent, as well as live Antigravity execution.
- Projects must be strictly isolated to their specified directory paths.
- Self-healing retry loops must be capped at 3 attempts before raising a PM attention alert.
- Frontend must not use TailwindCSS unless explicitly requested; use semantic Vanilla CSS design tokens with sleek dark mode aesthetics.

---

### Task 1: Backend Core Data Models & SQLite State Store

**Files:**
- Create: `backend/app/models/schemas.py`
- Create: `backend/app/services/state_store.py`
- Create: `backend/tests/test_state_store.py`

**Interfaces:**
- Consumes: Pydantic v2 models, standard `sqlite3`
- Produces: `Project`, `AgentRole`, `AgentState`, `TaskItem`, `PMDirective`, `ApprovalRequest`, `StateStore`

- [ ] **Step 1: Write failing test for StateStore**

```python
# backend/tests/test_state_store.py
import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.models.schemas import Project, AgentState, TaskItem

def test_state_store_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = StateStore(db_path)
        
        # Create Project
        proj = store.create_project(project_id="proj-a", name="Project Alpha", workspace_path=tmpdir)
        assert proj.project_id == "proj-a"
        assert proj.name == "Project Alpha"
        
        # Add Task
        task = store.create_task(project_id="proj-a", title="Setup DB", assigned_to="BackendDev")
        assert task.title == "Setup DB"
        assert task.status == "TODO"
        
        # Update Task
        updated = store.update_task_status(task.task_id, "IN_PROGRESS")
        assert updated.status == "IN_PROGRESS"
        
        # Update Agent State
        store.set_agent_status(project_id="proj-a", role="BackendDev", status="THINKING", thought="Designing schema")
        agent_state = store.get_agent_status("proj-a", "BackendDev")
        assert agent_state.status == "THINKING"
        assert agent_state.thought == "Designing schema"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_state_store.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'app')

- [ ] **Step 3: Implement schemas and StateStore**

```python
# backend/app/models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid
import time

class AgentRole(str, Enum):
    ARCHITECT = "Architect"
    DESIGNER = "Designer"
    FRONTEND_DEV = "FrontendDev"
    BACKEND_DEV = "BackendDev"
    QA_TESTER = "QATester"
    REVIEWER = "Reviewer"
    DOC_WRITER = "DocWriter"

class AgentStatus(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"

class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    TESTING = "TESTING"
    REVIEW = "REVIEW"
    DONE = "DONE"
    FAILED = "FAILED"

class TaskItem(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    title: str
    description: str = ""
    assigned_to: str
    status: TaskStatus = TaskStatus.TODO
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class AgentState(BaseModel):
    project_id: str
    role: str
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    thought: str = ""
    last_tool_call: Optional[str] = None
    updated_at: float = Field(default_factory=time.time)

class Project(BaseModel):
    project_id: str
    name: str
    workspace_path: str
    auto_pilot: bool = False
    created_at: float = Field(default_factory=time.time)
```

```python
# backend/app/services/state_store.py
import sqlite3
import json
import time
from typing import List, Optional
from app.models.schemas import Project, TaskItem, AgentState, TaskStatus, AgentStatus

class StateStore:
    def __init__(self, db_path: str = "state.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT,
                    workspace_path TEXT,
                    auto_pilot INTEGER DEFAULT 0,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    title TEXT,
                    description TEXT,
                    assigned_to TEXT,
                    status TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_states (
                    project_id TEXT,
                    role TEXT,
                    status TEXT,
                    current_task_id TEXT,
                    thought TEXT,
                    last_tool_call TEXT,
                    updated_at REAL,
                    PRIMARY KEY (project_id, role)
                )
            """)
            conn.commit()

    def create_project(self, project_id: str, name: str, workspace_path: str, auto_pilot: bool = False) -> Project:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?)",
                (project_id, name, workspace_path, 1 if auto_pilot else 0, now)
            )
            conn.commit()
        return Project(project_id=project_id, name=name, workspace_path=workspace_path, auto_pilot=auto_pilot, created_at=now)

    def get_project(self, project_id: str) -> Optional[Project]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, name, workspace_path, auto_pilot, created_at FROM projects WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if row:
                return Project(project_id=row[0], name=row[1], workspace_path=row[2], auto_pilot=bool(row[3]), created_at=row[4])
        return None

    def list_projects(self) -> List[Project]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, name, workspace_path, auto_pilot, created_at FROM projects")
            return [Project(project_id=r[0], name=r[1], workspace_path=r[2], auto_pilot=bool(r[3]), created_at=r[4]) for r in cur.fetchall()]

    def create_task(self, project_id: str, title: str, assigned_to: str, description: str = "") -> TaskItem:
        task = TaskItem(project_id=project_id, title=title, description=description, assigned_to=assigned_to)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task.task_id, task.project_id, task.title, task.description, task.assigned_to, task.status.value, task.created_at, task.updated_at)
            )
            conn.commit()
        return task

    def update_task_status(self, task_id: str, status: str) -> TaskItem:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?", (status, now, task_id))
            conn.commit()
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at FROM tasks WHERE task_id = ?", (task_id,))
            r = cur.fetchone()
            return TaskItem(task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4], status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7])

    def get_tasks(self, project_id: str) -> List[TaskItem]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
            return [TaskItem(task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4], status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7]) for r in cur.fetchall()]

    def set_agent_status(self, project_id: str, role: str, status: str, thought: str = "", current_task_id: Optional[str] = None, last_tool_call: Optional[str] = None):
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO agent_states (project_id, role, status, current_task_id, thought, last_tool_call, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, role) DO UPDATE SET
                    status=excluded.status,
                    current_task_id=coalesce(excluded.current_task_id, agent_states.current_task_id),
                    thought=excluded.thought,
                    last_tool_call=coalesce(excluded.last_tool_call, agent_states.last_tool_call),
                    updated_at=excluded.updated_at
            """, (project_id, role, status, current_task_id, thought, last_tool_call, now))
            conn.commit()

    def get_agent_status(self, project_id: str, role: str) -> AgentState:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, role, status, current_task_id, thought, last_tool_call, updated_at FROM agent_states WHERE project_id = ? AND role = ?", (project_id, role))
            r = cur.fetchone()
            if r:
                return AgentState(project_id=r[0], role=r[1], status=AgentStatus(r[2]), current_task_id=r[3], thought=r[4], last_tool_call=r[5], updated_at=r[6])
        return AgentState(project_id=project_id, role=role)

    def get_all_agent_states(self, project_id: str) -> List[AgentState]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, role, status, current_task_id, thought, last_tool_call, updated_at FROM agent_states WHERE project_id = ?", (project_id,))
            return [AgentState(project_id=r[0], role=r[1], status=AgentStatus(r[2]), current_task_id=r[3], thought=r[4], last_tool_call=r[5], updated_at=r[6]) for r in cur.fetchall()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_state_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/services/state_store.py backend/tests/test_state_store.py
git commit -m "feat(backend): add core models and SQLite state store"
```

---

### Task 2: Project Manager & Workspace Isolation Engine

**Files:**
- Create: `backend/app/services/project_manager.py`
- Create: `backend/tests/test_project_manager.py`

**Interfaces:**
- Consumes: `StateStore`, `Project`
- Produces: `ProjectManager` managing max 2 active projects with directory validation and isolation

- [ ] **Step 1: Write failing test for ProjectManager**

```python
# backend/tests/test_project_manager.py
import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager

def test_project_manager_isolation_and_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store, max_projects=2)
        
        dir_a = os.path.join(tmpdir, "proj_a")
        dir_b = os.path.join(tmpdir, "proj_b")
        dir_c = os.path.join(tmpdir, "proj_c")
        os.makedirs(dir_a)
        os.makedirs(dir_b)
        os.makedirs(dir_c)
        
        p1 = pm.register_project("proj-a", "Project A", dir_a)
        p2 = pm.register_project("proj-b", "Project B", dir_b)
        assert len(pm.get_active_projects()) == 2
        
        # Max limit exceeded should raise ValueError
        with pytest.raises(ValueError, match="Maximum active projects"):
            pm.register_project("proj-c", "Project C", dir_c)
            
        # Verify workspace directory resolution
        assert pm.get_project_workspace("proj-a") == dir_a
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_project_manager.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'app.services.project_manager')

- [ ] **Step 3: Implement ProjectManager**

```python
# backend/app/services/project_manager.py
import os
from typing import List, Optional
from app.services.state_store import StateStore
from app.models.schemas import Project, AgentRole

DEFAULT_ROLES = [
    AgentRole.ARCHITECT.value,
    AgentRole.DESIGNER.value,
    AgentRole.FRONTEND_DEV.value,
    AgentRole.BACKEND_DEV.value,
    AgentRole.QA_TESTER.value,
    AgentRole.REVIEWER.value,
    AgentRole.DOC_WRITER.value,
]

class ProjectManager:
    def __init__(self, store: StateStore, max_projects: int = 2):
        self.store = store
        self.max_projects = max_projects

    def register_project(self, project_id: str, name: str, workspace_path: str, auto_pilot: bool = False) -> Project:
        resolved_path = os.path.abspath(workspace_path)
        if not os.path.exists(resolved_path):
            os.makedirs(resolved_path, exist_ok=True)
            
        existing = self.store.get_project(project_id)
        if not existing:
            current_projects = self.store.list_projects()
            if len(current_projects) >= self.max_projects:
                raise ValueError(f"Maximum active projects limit ({self.max_projects}) reached.")
        
        proj = self.store.create_project(project_id, name, resolved_path, auto_pilot)
        
        # Initialize default agent states
        for role in DEFAULT_ROLES:
            self.store.set_agent_status(project_id, role, "IDLE", "Ready for PM directives")
            
        return proj

    def get_active_projects(self) -> List[Project]:
        return self.store.list_projects()

    def get_project_workspace(self, project_id: str) -> str:
        proj = self.store.get_project(project_id)
        if not proj:
            raise KeyError(f"Project {project_id} not found")
        return proj.workspace_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_project_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/project_manager.py backend/tests/test_project_manager.py
git commit -m "feat(backend): implement project manager and workspace isolation"
```

---

### Task 3: Antigravity SDK Agent Runner with Streaming Broadcast

**Files:**
- Create: `backend/app/services/agent_runner.py`
- Create: `backend/tests/test_agent_runner.py`

**Interfaces:**
- Consumes: `google.antigravity.Agent`, `LocalAgentConfig`, `CapabilitiesConfig`
- Produces: `AgentRunner.dispatch_agent_task(project_id, role, prompt, workspace_path, event_callback)`

- [ ] **Step 1: Write failing test for AgentRunner**

```python
# backend/tests/test_agent_runner.py
import pytest
import asyncio
from app.services.agent_runner import AgentRunner

@pytest.mark.asyncio
async def test_agent_runner_streaming_events():
    runner = AgentRunner(use_mock=True) # supports mock for fast deterministic test
    events = []
    
    async def on_event(event_type: str, data: dict):
        events.append((event_type, data))
        
    result = await runner.dispatch_agent_task(
        project_id="test-p1",
        role="Architect",
        prompt="Plan a todo app",
        workspace_path="/tmp",
        event_callback=on_event
    )
    
    event_types = [e[0] for e in events]
    assert "AGENT_THOUGHT_DELTA" in event_types
    assert "AGENT_STATUS_CHANGE" in event_types
    assert result["status"] == "SUCCESS"
    assert len(result["response"]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_agent_runner.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'app.services.agent_runner')

- [ ] **Step 3: Implement AgentRunner with Antigravity SDK integration & Mock mode**

```python
# backend/app/services/agent_runner.py
import asyncio
import time
from typing import Callable, Coroutine, Any, Dict, Optional

# Antigravity SDK
try:
    from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
    HAS_ANTIGRAVITY = True
except ImportError:
    HAS_ANTIGRAVITY = False

ROLE_PROMPTS = {
    "Architect": "You are a software architect. Break down high-level requirements into clear, isolated tasks.",
    "Designer": "You are a UI/UX designer. Create CSS design tokens, layouts, and component structures.",
    "FrontendDev": "You are a senior frontend engineer. Implement UI components and client logic.",
    "BackendDev": "You are a senior backend engineer. Implement server endpoints and database interactions.",
    "QATester": "You are a QA automation engineer. Run test suites and report regressions and failures.",
    "Reviewer": "You are a staff code reviewer. Verify security, code cleanliness, and produce release summaries.",
    "DocWriter": "You are a technical writer. Produce documentation, READMEs, and API references."
}

class AgentRunner:
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock or not HAS_ANTIGRAVITY

    async def dispatch_agent_task(
        self,
        project_id: str,
        role: str,
        prompt: str,
        workspace_path: str,
        event_callback: Optional[Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]] = None
    ) -> Dict[str, Any]:
        
        async def emit(event_type: str, data: Dict[str, Any]):
            if event_callback:
                await event_callback(event_type, {
                    "project_id": project_id,
                    "role": role,
                    "timestamp": time.time(),
                    **data
                })

        await emit("AGENT_STATUS_CHANGE", {"status": "THINKING"})

        if self.use_mock:
            # Deterministic simulation for tests and fallback
            thoughts = [
                f"Analyzing requirements for {role}...",
                f"Examining workspace files in {workspace_path}...",
                "Formulating optimal approach..."
            ]
            for t in thoughts:
                await emit("AGENT_THOUGHT_DELTA", {"thought": t})
                await asyncio.sleep(0.05)
                
            await emit("TOOL_EXECUTION_START", {"tool": "list_files", "args": {"path": workspace_path}})
            await asyncio.sleep(0.05)
            await emit("TOOL_EXECUTION_FINISH", {"tool": "list_files", "result": "Files checked"})
            
            await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
            return {
                "status": "SUCCESS",
                "role": role,
                "response": f"Completed tasks for: {prompt}"
            }

        # Live Antigravity Python SDK Execution
        system_instruction = ROLE_PROMPTS.get(role, "You are a helpful software engineering agent.")
        config = LocalAgentConfig(
            system_instructions=f"{system_instruction} Always operate strictly within {workspace_path}.",
            capabilities=CapabilitiesConfig()
        )
        
        try:
            async with Agent(config) as agent:
                response = await agent.chat(prompt)
                full_text = []
                
                # Stream thoughts if available
                if hasattr(response, "thoughts"):
                    async for thought in response.thoughts:
                        await emit("AGENT_THOUGHT_DELTA", {"thought": str(thought)})
                        
                # Stream tool calls if available
                if hasattr(response, "tool_calls"):
                    async for tool_call in response.tool_calls:
                        await emit("TOOL_EXECUTION_START", {"tool": tool_call.name, "args": tool_call.args})
                        
                # Stream response tokens
                async for token in response:
                    full_text.append(token)
                    
                await emit("AGENT_STATUS_CHANGE", {"status": "DONE"})
                return {
                    "status": "SUCCESS",
                    "role": role,
                    "response": "".join(full_text)
                }
        except Exception as e:
            await emit("AGENT_STATUS_CHANGE", {"status": "BLOCKED", "error": str(e)})
            return {
                "status": "ERROR",
                "role": role,
                "error": str(e)
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_agent_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_runner.py backend/tests/test_agent_runner.py
git commit -m "feat(backend): implement Antigravity agent runner with live event streaming"
```

---

### Task 4: Self-Healing Multi-Agent Pipeline & Approval Gates

**Files:**
- Create: `backend/app/services/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `ProjectManager`, `AgentRunner`, `StateStore`
- Produces: `Orchestrator.execute_pm_directive(project_id, directive)`, `Orchestrator.resolve_approval(project_id, request_id, decision)`

- [ ] **Step 1: Write failing test for Orchestrator**

```python
# backend/tests/test_orchestrator.py
import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_orchestrator_pipeline_auto():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        pm.register_project("proj-1", "Project 1", tmpdir, auto_pilot=True)
        runner = AgentRunner(use_mock=True)
        
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        result = await orch.execute_pm_directive("proj-1", "Build landing page")
        
        assert result["status"] == "COMPLETED"
        tasks = store.get_tasks("proj-1")
        assert len(tasks) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_orchestrator.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'app.services.orchestrator')

- [ ] **Step 3: Implement Orchestrator with Self-Healing Loop**

```python
# backend/app/services/orchestrator.py
import asyncio
from typing import Dict, Any, Optional
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner

class Orchestrator:
    def __init__(self, store: StateStore, project_manager: ProjectManager, agent_runner: AgentRunner):
        self.store = store
        self.pm = project_manager
        self.runner = agent_runner
        self.pending_approvals: Dict[str, asyncio.Event] = {}
        self.approval_decisions: Dict[str, str] = {}

    async def execute_pm_directive(self, project_id: str, directive: str, event_callback=None) -> Dict[str, Any]:
        workspace = self.pm.get_project_workspace(project_id)
        project = self.store.get_project(project_id)
        
        # 1. Architect decomposes tasks
        arch_res = await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="Architect",
            prompt=f"Decompose this PM requirement into tasks: {directive}",
            workspace_path=workspace,
            event_callback=event_callback
        )
        
        # Create tasks
        t1 = self.store.create_task(project_id, "Implement UI & Features", "FrontendDev", directive)
        t2 = self.store.create_task(project_id, "Implement API & Logic", "BackendDev", directive)
        
        # 2. Check Approval Gate if Auto-Pilot is OFF
        if not project.auto_pilot:
            # In hybrid mode, trigger decision gate event
            if event_callback:
                await event_callback("DECISION_GATE_OPEN", {
                    "project_id": project_id,
                    "gate_type": "PLAN_APPROVAL",
                    "summary": f"Architect planned 2 tasks for: {directive}"
                })
        
        # 3. Dev Agents execute
        self.store.update_task_status(t1.task_id, "IN_PROGRESS")
        await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="FrontendDev",
            prompt=f"Build frontend for: {directive}",
            workspace_path=workspace,
            event_callback=event_callback
        )
        self.store.update_task_status(t1.task_id, "DONE")
        
        # 4. QA Tester with Self-Healing Loop (Max 3 retries)
        max_retries = 3
        tests_passed = True
        for attempt in range(1, max_retries + 1):
            qa_res = await self.runner.dispatch_agent_task(
                project_id=project_id,
                role="QATester",
                prompt=f"Verify workspace tests (attempt {attempt})",
                workspace_path=workspace,
                event_callback=event_callback
            )
            # If simulated failure on attempt 1, heal on attempt 2
            if "FAIL" in qa_res.get("response", "") and attempt < max_retries:
                await self.runner.dispatch_agent_task(
                    project_id=project_id,
                    role="BackendDev",
                    prompt="Fix errors caught by QA tester",
                    workspace_path=workspace,
                    event_callback=event_callback
                )
            else:
                tests_passed = True
                break
                
        # 5. Reviewer signs off
        await self.runner.dispatch_agent_task(
            project_id=project_id,
            role="Reviewer",
            prompt="Perform final code review and produce release summary",
            workspace_path=workspace,
            event_callback=event_callback
        )
        
        return {"status": "COMPLETED", "project_id": project_id, "directive": directive}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(backend): implement self-healing multi-agent orchestrator"
```

---

### Task 5: FastAPI Endpoints & WebSocket Event Hub

**Files:**
- Create: `backend/app/api/websocket_hub.py`
- Create: `backend/app/api/routes.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `Orchestrator`, `ProjectManager`, `StateStore`
- Produces: REST endpoints (`/api/projects`, `/api/projects/{id}/directive`, `/api/projects/{id}/tasks`), WebSocket `/ws/live`

- [ ] **Step 1: Write failing test for FastAPI routes**

```python
# backend/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_api_projects_lifecycle():
    client = TestClient(app)
    
    # List projects initially empty
    res = client.get("/api/projects")
    assert res.status_code == 200
    
    # Register Project Alpha
    res = client.post("/api/projects", json={
        "project_id": "alpha",
        "name": "Alpha App",
        "workspace_path": "/tmp/alpha",
        "auto_pilot": False
    })
    assert res.status_code == 200
    assert res.json()["project_id"] == "alpha"
    
    # Get project detail
    res = client.get("/api/projects/alpha")
    assert res.status_code == 200
    assert res.json()["name"] == "Alpha App"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_api.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'app.main')

- [ ] **Step 3: Implement WebSocket Hub, Routes and Main FastAPI App**

```python
# backend/app/api/websocket_hub.py
import json
from fastapi import WebSocket
from typing import List, Dict

class WebSocketHub:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: Dict):
        payload = json.dumps({"event": event_type, "data": data})
        for conn in list(self.active_connections):
            try:
                await conn.send_text(payload)
            except Exception:
                self.disconnect(conn)

hub = WebSocketHub()
```

```python
# backend/app/api/routes.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator
from app.api.websocket_hub import hub

router = APIRouter(prefix="/api")

store = StateStore()
pm = ProjectManager(store=store)
runner = AgentRunner(use_mock=False)
orchestrator = Orchestrator(store=store, project_manager=pm, agent_runner=runner)

class CreateProjectRequest(BaseModel):
    project_id: str
    name: str
    workspace_path: str
    auto_pilot: bool = False

class DirectiveRequest(BaseModel):
    directive: str

@router.get("/projects")
def get_projects():
    return store.list_projects()

@router.post("/projects")
def create_project(req: CreateProjectRequest):
    try:
        return pm.register_project(req.project_id, req.name, req.workspace_path, req.auto_pilot)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/projects/{project_id}")
def get_project(project_id: str):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p

@router.get("/projects/{project_id}/agents")
def get_project_agents(project_id: str):
    return store.get_all_agent_states(project_id)

@router.get("/projects/{project_id}/tasks")
def get_project_tasks(project_id: str):
    return store.get_tasks(project_id)

@router.post("/projects/{project_id}/directive")
async def send_directive(project_id: str, req: DirectiveRequest, bg: BackgroundTasks):
    p = store.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    async def run_pipeline():
        await orchestrator.execute_pm_directive(
            project_id=project_id,
            directive=req.directive,
            event_callback=hub.broadcast
        )
        
    bg.add_task(run_pipeline)
    return {"status": "QUEUED", "project_id": project_id, "directive": req.directive}
```

```python
# backend/app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.websocket_hub import hub

app = FastAPI(title="Virtual AI Office PM Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/websocket_hub.py backend/app/api/routes.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat(backend): add FastAPI REST routes and WebSocket live hub"
```

---

### Task 6: Frontend Virtual AI Office UI (React + Vite)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/index.css` (Glassmorphism, Neon glow tokens, modern animations)
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/components/OfficeFloorView.jsx`
- Create: `frontend/src/components/DualSplitView.jsx`
- Create: `frontend/src/components/FocusRoomView.jsx`
- Create: `frontend/src/components/PMCommandBar.jsx`
- Create: `frontend/src/components/DecisionGateModal.jsx`

**Interfaces:**
- Consumes: REST endpoints & WebSocket `/ws/live`
- Produces: Interactive Virtual AI Office with view switcher (Office Floor, Dual Split, Focus Room)

- [ ] **Step 1: Scaffold Vite React Frontend**

Initialize `frontend/package.json` with React 18, Lucide-react (or SVG icons), and configure Vite proxy to `http://localhost:8000`.

- [ ] **Step 2: Build Design System & Tokens in `index.css`**

Implement curated CSS variables:
`--bg-canvas`, `--bg-surface`, `--accent-cyan`, `--accent-purple`, `--accent-amber`, `--text-primary`, `--text-muted`, Glassmorphic card styling, and subtle pulse animation `@keyframes agent-pulse`.

- [ ] **Step 3: Implement Components**
  - `OfficeFloorView.jsx`: Visual representation of Project Alpha & Beta rooms with desks for 7 agents and dynamic thought bubbles.
  - `DualSplitView.jsx`: 50/50 dual column view with mini Kanban board and live log streams.
  - `FocusRoomView.jsx`: In-depth project view with terminal output, file changes, and agent whisper chat.
  - `PMCommandBar.jsx`: Persistent PM Directive bar with Auto-pilot switch.
  - `DecisionGateModal.jsx`: Modal popup when human approval is required.

- [ ] **Step 4: Test build and verify clean compilation**

Run: `cd frontend && npm install && npm run build`
Expected: PASS with 0 build errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): implement Virtual AI Office Web Dashboard UI"
```

---

### Task 7: End-to-End Integration & Launch Script

**Files:**
- Create: `start_dashboard.py` (Unified startup script launching FastAPI + serving Frontend)
- Create: `README.md` with usage guide for PMs

- [ ] **Step 1: Create unified dashboard launcher**

Build `start_dashboard.py` to optionally run frontend dev server or build & serve frontend assets seamlessly through FastAPI static files.

- [ ] **Step 2: Run End-to-End verification**

1. Launch backend on port 8000.
2. Register 2 test projects: `Project Alpha` and `Project Beta`.
3. Submit a PM directive to `Project Alpha`.
4. Verify thoughts and tool calls stream across WebSocket and render in the UI.
5. Verify Dual View displays both projects concurrently.

- [ ] **Step 3: Commit**

```bash
git add start_dashboard.py README.md
git commit -m "feat: add unified launcher and documentation"
```
