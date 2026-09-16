# 🏢 Antigravity Virtual AI Office — PM Command Center

A modern, cyberpunk-aesthetic **Multi-Agent Orchestrator & Virtual Office Dashboard** powered by FastAPI and the **Antigravity Python SDK (`google-antigravity`)**.

Manage teams of 5–10 autonomous agents across up to 2 concurrent projects. Simply input high-level product requirements as a Product Manager (PM), while the agents autonomously decompose, build, test, self-heal, and review your code!

---

## ✨ Key Features

1. **🏢 Virtual Office Floor**:
   - Visual department rooms for **Project Alpha** and **Project Beta**.
   - Interactive agent desks with animated avatars for:
     - 📐 **Product Architect**: Decomposes requirements into user stories and task trees.
     - 🎨 **UI/UX Designer**: Designs responsive layout and styling tokens.
     - 💻 **Frontend Dev**: Builds components, client state, and views.
     - ⚙️ **Backend Dev**: Implements endpoints, server logic, and database layer.
     - 🧪 **QA Tester**: Executes automated test suites and regression checks.
     - 🛡️ **Code Reviewer**: Audits security, diff quality, and writes PM release notes.
     - 📝 **Doc Writer**: Updates documentation and guides.
   - Live thought bubbles and glowing pulse rings indicating active thoughts/actions.

2. **⚡ Dual-Split Screen (Multitasking)**:
   - 50/50 two-column interface for simultaneous management of 2 projects.
   - Real-time mini Kanban boards (To Do, In Progress, Done).
   - Real-time terminal feeds displaying thoughts, tool calls, and test results.

3. **🔍 Focus War Room**:
   - Deep dive into a single project with full agent rosters and extended thought logs.

4. **🎯 PM Command Desk & Hybrid Controls**:
   - **PM Directive Box**: Enter high-level requests (e.g. *"Add Google OAuth2 and profile dashboard"*).
   - **Auto-Pilot vs Gate Mode**: Toggle between 100% autonomous execution or human-in-the-loop approval checkpoints.
   - **Agent Whisper**: Click any agent at their desk to whisper direct constraints mid-sprint without starting over.
   - **Self-Healing Loop**: If the QA tester catches failures, logs are automatically fed back to Dev agents to self-heal and retry (capped at 3 iterations).

---

## 🚀 Quickstart & Setup

### 1. Install Dependencies

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies and build production assets:

```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Configure Environment (Optional)

Copy `.env.example` to `.env` if you wish to configure your Gemini API Key or custom Antigravity Skills directory:

```bash
cp .env.example .env
```

### 3. Launch the Dashboard

Run the startup script:

**On Windows:**
Double-click `start.bat` or run:

```powershell
python start_dashboard.py
```

**On Linux / macOS:**

```bash
python3 start_dashboard.py
```

### 4. Open Your Browser

Navigate to:

```
http://127.0.0.1:8000
```

---

## 🧪 Running Automated Tests

Run the full pytest suite (63/63 passing):

```bash
# Windows (PowerShell)
$env:PYTHONPATH="backend;.backend"; python -m pytest backend/tests/ -v

# Linux / macOS
PYTHONPATH=backend python3 -m pytest backend/tests/ -v
```
