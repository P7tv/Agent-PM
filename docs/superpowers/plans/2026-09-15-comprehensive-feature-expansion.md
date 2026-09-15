# Complete Feature Expansion Suite for Agent-PM

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full suite of gap features (Console Persistence, Granular Sprint Tasks, Git Remote & Branching, Backlog Board, Queue Priority/Reorder, Agent Memory/Journal, Agent Performance Metrics, and File Diff Preview) into Agent-PM.

**Architecture:** Extend SQLite schema in `state_store.py` with backward-compatible tables/columns, integrate state management into `ConsoleService`, `Orchestrator`, `GitService`, and `AgentRunner`, expose unified REST endpoints in `routes.py`, and render responsive visual controls in the React dashboard frontend.

**Tech Stack:** FastAPI, Python SQLite3, React (Vite), Lucide-React, WebSocket.

---

## Task 1: Console SQLite Persistence (Phase 1)

**Files:**
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/services/console_service.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_console_persistence.py`

- [ ] **Step 1: Write failing tests for Console SQLite Persistence**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement database table and methods in `state_store.py` and connect `console_service.py`**
- [ ] **Step 4: Run test to verify it passes**

---

## Task 2: Granular Sprint Task Tracking & Output Summaries (Phase 1)

**Files:**
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/services/orchestrator.py`
- Modify: `backend/app/api/routes.py`
- Modify: `frontend/src/components/SprintHistoryPanel.jsx`
- Test: `backend/tests/test_sprint_granular_tasks.py`

- [ ] **Step 1: Write failing tests for Sprint Granular Tasks**
- [ ] **Step 2: Add `sprint_id` and `result_output` to `tasks` in `state_store.py` and link in `orchestrator.py`**
- [ ] **Step 3: Expose sprint tasks API in `routes.py` and build expandable accordion in `SprintHistoryPanel.jsx`**
- [ ] **Step 4: Verify tests pass**

---

## Task 3: File Diff Preview Before Applying Proposals (Phase 1)

**Files:**
- Create: `frontend/src/components/chat/DiffPreviewModal.jsx`
- Modify: `frontend/src/components/chat/ChatMessageItem.jsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Create `DiffPreviewModal.jsx` with line-by-line colored diff preview**
- [ ] **Step 2: Connect "Review & Apply" button in `ChatMessageItem.jsx` to open modal**
- [ ] **Step 3: Add CSS styling for diff view**

---

## Task 4: Product Backlog Board & Sprint Planning (Phase 2)

**Files:**
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/api/routes.py`
- Create: `frontend/src/components/BacklogBoardModal.jsx`
- Modify: `frontend/src/components/PMCommandBar.jsx` & `frontend/src/components/FocusRoomView.jsx`
- Test: `backend/tests/test_backlog_service.py`

- [ ] **Step 1: Write failing test for Backlog store and API**
- [ ] **Step 2: Add `backlog_items` in `state_store.py` and routes in `routes.py`**
- [ ] **Step 3: Implement `BacklogBoardModal.jsx` in frontend**
- [ ] **Step 4: Verify tests pass**

---

## Task 5: Directive Queue Priority & Reordering (Phase 2)

**Files:**
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/services/sprint_queue.py`
- Modify: `backend/app/api/routes.py`
- Modify: `frontend/src/App.jsx`
- Test: `backend/tests/test_queue_priority.py`

- [ ] **Step 1: Write test for Queue priority and reordering**
- [ ] **Step 2: Implement priority and move up/down methods**
- [ ] **Step 3: Update Queue Drawer UI in `App.jsx` with controls**
- [ ] **Step 4: Verify tests pass**

---

## Task 6: Agent Memory & Project Journal (Phase 2)

**Files:**
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/services/agent_runner.py`
- Modify: `backend/app/services/orchestrator.py`
- Modify: `backend/app/api/routes.py`
- Create: `frontend/src/components/ProjectJournalModal.jsx`
- Modify: `frontend/src/components/FocusRoomView.jsx`
- Test: `backend/tests/test_project_memory.py`

- [ ] **Step 1: Write test for Project Memory persistence and agent prompt injection**
- [ ] **Step 2: Implement `project_memories` table in `state_store.py` and prompt synthesis in `agent_runner.py`**
- [ ] **Step 3: Create `ProjectJournalModal.jsx` UI and routes in `routes.py`**
- [ ] **Step 4: Verify tests pass**

---

## Task 7: Git Remote & Branch Management (Phase 3)

**Files:**
- Modify: `backend/app/services/git_service.py`
- Modify: `backend/app/api/routes.py`
- Modify: `frontend/src/components/FocusRoomView.jsx`
- Test: `backend/tests/test_git_remote_and_branch.py`

- [ ] **Step 1: Write test for git remote, push, pull, and branch operations in `git_service.py`**
- [ ] **Step 2: Implement methods in `git_service.py` and endpoints in `routes.py`**
- [ ] **Step 3: Add Remote bar & Branch switcher to "Code & Changes" tab in `FocusRoomView.jsx`**
- [ ] **Step 4: Verify tests pass**

---

## Task 8: Agent Performance & Activity Log (Phase 3)

**Files:**
- Modify: `backend/app/services/state_store.py`
- Modify: `backend/app/services/orchestrator.py`
- Modify: `backend/app/api/routes.py`
- Modify: `frontend/src/components/FocusRoomView.jsx`
- Test: `backend/tests/test_agent_metrics.py`

- [ ] **Step 1: Write test for `agent_activity_logs` metrics aggregation**
- [ ] **Step 2: Implement tracking in `orchestrator.py` and API endpoints in `routes.py`**
- [ ] **Step 3: Display metrics pills on agent cards and add activity log modal**
- [ ] **Step 4: Verify tests pass**

---

## Task 9: Full Regression & Integration Verification (Phase 4)

- [ ] **Step 1: Run all existing 93 pytest tests + new test files**
- [ ] **Step 2: Verify frontend compilation and UI interactions**
