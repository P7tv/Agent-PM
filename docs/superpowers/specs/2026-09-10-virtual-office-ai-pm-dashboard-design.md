# Design Specification: Virtual AI Office PM Dashboard

- **Date**: 2026-09-10
- **Author**: Antigravity & User Pair
- **Status**: Approved (Brainstorming Phase Completed)
- **Target Repository**: `/Users/panpan/My PM`

---

## 1. Executive Summary & Vision

The **Virtual AI Office PM Dashboard** is a local web application that transforms the user from an overburdened prompt-writer into an agile **AI Engineering Manager / Product Manager (PM)**. 

Instead of manually crafting verbose prompts across multiple chat windows in the Antigravity IDE, the user inputs high-level goals and product requirements. A team of **5–10 specialized AI Agents** (Software House preset) autonomously decomposes, implements, tests, fixes, and reviews tasks across **up to 2 concurrent projects**.

The interface simulates an interactive **Virtual AI Office**, providing real-time transparency into the agents' internal thoughts and tool actions while offering flexible **Hybrid Mode** control (allowing autonomous flow with manual PM intervention and decision gates).

---

## 2. Core Personas & Agent Team Roster

Each project instance runs an isolated team of specialized AI agents built on top of the **Antigravity Python SDK (`google-antigravity`)**:

| Role | Avatar & Name | Responsibilities | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **1. Product Architect** | 📐 `Architect` | Decomposes PM goals into user stories, technical specs, and dependency trees. | Read codebase, create implementation specs |
| **2. UI/UX Designer** | 🎨 `Designer` | Designs tokens, CSS styling, responsive wireframes, and design consistency. | CSS/Styling tools, component design |
| **3. Frontend Engineer** | 💻 `FrontendDev`| Builds UI components, client routing, forms, client state management. | File edits, frontend builds |
| **4. Backend Engineer** | ⚙️ `BackendDev` | Implements API endpoints, business logic, databases, background jobs. | File edits, server scripts |
| **5. QA & Test Runner** | 🧪 `QATester` | Executes automated test suites, linting, catches regressions, reproduces bugs. | `run_command` (pytest, npm test, etc.) |
| **6. Code Reviewer** | 🛡️ `Reviewer` | Verifies code quality, security standards, git diffs, produces PM release notes. | Read diffs, approval signing |
| **7. Tech Writer** | 📝 `DocWriter` | Writes API docs, updates READMEs, changelogs, and user guides. | Markdown generation, doc updates |

---

## 3. UI/UX Design: The Virtual Office Experience

The frontend is a modern web application built with **React/Vite** and a curated dark/cyberpunk aesthetic (glassmorphism, subtle glowing status rings, micro-animations).

### 3.1 Three Core Views (View Switcher)
1. **🏢 Office Floor View (Overview & Command Center)**:
   - Displays two visual rooms side-by-side: **Room Alpha (Project A)** and **Room Beta (Project B)**.
   - Each room shows desks/avatars for the 7 active agents.
   - **Interactive Agent Badges**:
     - 🟣 *Thinking*: Animated pulse ring + thought bubble summarizing the reasoning step.
     - 🔵 *Working*: Flashing tool icon indicating active file write or command execution.
     - 🟢 *Idle / Completed*: Resting state, ready for next queue item.
     - 🟠 *Attention Needed / Blocked*: Glowing amber alert when human PM input is requested.
2. **⚡ Split-Screen Dual View (Multitasking Operations)**:
   - 50/50 two-column split screen for active dual-project management.
   - Each column contains:
     - Project Header & Workspace path.
     - PM Directive Input Bar.
     - Mini Kanban Board (Backlog, In Progress, QA Testing, Done).
     - Live Event Stream (Agent thoughts and terminal command outputs).
3. **🔍 Focus Room View (Deep Dive)**:
   - Full-screen deep dive into a single project.
   - Tabs:
     - **War Room Chat**: Unified agent team conversation feed.
     - **File Changes / Git Diff**: Visual inspector of all modified files.
     - **Terminal & Test Output**: Live execution output of pytest / npm tests.
     - **1-on-1 Whisper**: Direct prompt channel to a specific agent.

### 3.2 PM Control Desk (Hybrid Interventions)
- **Top Command Bar**: High-level prompt box where the PM inputs the overall feature/bugfix request.
- **Auto-Pilot Toggle**: Switch per project to toggle between 100% autonomous pipeline and Step-by-Step Approval Gates.
- **Decision Gate Modal**: Whenever the Architect finishes planning or a critical architectural fork occurs, a modal surfaces:
  - `[ Approve & Proceed ]`
  - `[ Inject Feedback / Refine ]`
  - `[ Let AI Decide ]`
- **Whisper / Quick Intervene**: Clicking any agent allows the PM to inject immediate constraints (e.g., *"Make sure to use SQLite instead of PostgreSQL"*).

---

## 4. Technical Architecture & Backend Orchestrator

```
┌───────────────────────────────────────────────────────────┐
│                    Frontend (React / Vite)                │
│       Office Floor  │  Dual-Split View  │  Focus Room     │
└─────────────────────────────▲─────────────────────────────┘
                              │
              WebSocket + REST (JSON Events)
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                 FastAPI Orchestrator Server                │
│                                                           │
│  ┌─────────────────────────┐   ┌────────────────────────┐ │
│  │ Project A Controller    │   │ Project B Controller   │ │
│  │ ├─ Workspace: /path/A   │   │ ├─ Workspace: /path/B  │ │
│  │ ├─ State & Task Queue   │   │ ├─ State & Task Queue  │ │
│  │ └─ Agent Pool (SDK)     │   │ └─ Agent Pool (SDK)    │ │
│  └─────────────────────────┘   └────────────────────────┘ │
│                                                           │
│  [Event Dispatcher]  [SQLite State Store]  [Logger]       │
└─────────────────────────────▲─────────────────────────────┘
                              │
                     Async Context Pool
                              │
┌─────────────────────────────▼─────────────────────────────┐
│             google.antigravity Python SDK                 │
│   Agent(LocalAgentConfig(system_instructions, tools))     │
│   - Streaming thoughts: `response.thoughts`              │
│   - Streaming tool calls: `response.tool_calls`           │
└───────────────────────────────────────────────────────────┘
```

### 4.1 Backend Engine Components (Python FastAPI)
1. **`ProjectManager`**:
   - Manages configuration, working directory path, and concurrency for up to 2 active projects.
   - Enforces workspace isolation: each project runs commands strictly inside its configured `Cwd`.
2. **`AgentRunner` (SDK Wrapper)**:
   - Instantiates `Agent` using `google.antigravity.Agent` and `LocalAgentConfig`.
   - Attaches streaming consumers to `response.thoughts` and `response.tool_calls`.
   - Emits structured JSON events over WebSocket:
     - `AGENT_THOUGHT_DELTA`: Real-time reasoning tokens.
     - `TOOL_EXECUTION_START`: Tool name and arguments.
     - `TOOL_EXECUTION_FINISH`: Tool result / exit code.
     - `TASK_STATUS_CHANGE`: Status transition (Pending -> In Progress -> Testing -> Done).
3. **`SelfHealingOrchestrator`**:
   - Automatically chains tasks:
     - `Architect` -> generates plan tasks.
     - `Dev` -> writes code.
     - `QA` -> executes test runner (`pytest` or `npm test`).
     - *If test fails*: Error log is packaged and fed back to `Dev` with prompt: *"Fix this error. Repeat QA until green."* (Max retries: 3).
     - *If test passes*: Automatically hands off to `Reviewer` -> generates release summary.
4. **`StateStore` (SQLite)**:
   - Persists project paths, task board states, agent chat logs, and approval requests so browser reloads retain full history.

---

## 5. Security & Isolation

- **File Boundary**: Agents are constrained to the designated project root directory.
- **Safety Capabilities**: Dangerous system actions require PM Gate or capability whitelist (`CapabilitiesConfig`).
- **Loop Prevention**: Self-healing retry loops are strictly bounded to 3 iterations before falling back to PM intervention.

---

## 6. Verification Plan

1. **Backend Unit & Integration Tests**:
   - Test `ProjectManager` isolation with two test directories.
   - Test WebSocket broadcast of mock agent thought and tool call events.
   - Test self-healing pipeline state transitions (Failure -> Retry -> Success).
2. **Frontend UI Tests**:
   - Verify layout switching between Office Floor, Split Dual-View, and Focus Room.
   - Verify real-time updates of agent avatar animations and thought bubbles.
   - Verify PM Directive submission and Decision Gate interactions.
3. **End-to-End Test**:
   - Run a live sample project (e.g., a simple web app or CLI utility) in Project A while monitoring Project B concurrently.
   - Confirm PM inputs a single goal and agents complete the cycle autonomously.
