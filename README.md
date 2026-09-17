# 🏢 Antigravity Virtual AI Office — PM Command Center

A modern, cyberpunk-aesthetic **Multi-Agent Orchestrator & Virtual Office Dashboard** powered by FastAPI and the **Antigravity Python SDK (`google-antigravity`)**.

Agent-PM coordinates coding agents from a product request. It selects relevant roles, plans the work, edits a staged source copy, runs project checks, and reviews changes before delivery. The dashboard shows progress, questions, file evidence, and recovery controls.

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
   - Activity feeds showing visible progress, tool steps, file evidence, and test results.

3. **🔍 Focus War Room**:
   - Deep dive into a single project with full agent rosters and extended thought logs.

4. **🎯 PM Command Desk & Hybrid Controls**:
   - **PM Directive Box**: Enter high-level requests (e.g. *"Add Google OAuth2 and profile dashboard"*).
   - **Auto-Pilot vs Gate Mode**: Toggle between 100% autonomous execution or human-in-the-loop approval checkpoints.
   - **Agent Whisper**: Click any agent at their desk to whisper direct constraints mid-sprint without starting over.
     - Instructions are saved to the active sprint and used at the next safe agent step. They do not inject into a running tool call or launch a separate writer in the project folder. Pending instructions block delivery.
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

### Workspace and delivery checks

New checkpoints persist their initial source baseline and a manifest hash. Resume compares against that original baseline, so conflicting human edits are preserved and block delivery. Older checkpoints without this baseline remain available for file recovery but cannot automatically Resume.

Code delivery requires a successful test command; build/typecheck alone is insufficient. Reports distinguish automated checks from acceptance criteria that have not been independently verified. A completed run does not imply production readiness.

Workflow safety regression tests: `PYTHONPATH=backend pytest -q backend/tests/test_workflow_safety.py`.

Run the full pytest suite:

```bash
# Windows (PowerShell)
$env:PYTHONPATH="backend;.backend"; python -m pytest backend/tests/ -v

# Linux / macOS
PYTHONPATH=backend python3 -m pytest backend/tests/ -v
```

## Workflow controls and evidence

- **Pause** stops the active process and preserves partial source. **Resume** inspects unfinished work in the same staged workspace. Completed writers are reused only when the checkpoint revision is unchanged. CLI sessions resume by the exact conversation ID and feature/task key when available; SDK runs reconcile from files.
- Restarted runs are **INTERRUPTED**. Restart does not approve a pending question or automatically resume a paused project.
- **ลองไฟล์พักงาน** starts a checkpoint preview using the project's configured `preview` command. This preview is separate from delivered project files. Resume stops a checkpoint preview before continuing.
- CLI tool steps stream into the activity feed. Recent events replay after page reload; reconnect replays after the last sequence. The journal retains 10,000 events and hides raw tool parameters/outputs. Replay does not reopen old decision dialogs.
- Runtime selection: `AGENT_RUNTIME=auto` prefers CLI, with SDK when CLI is unavailable. Use `cli` or `sdk` to select explicitly. `AGENT_MODEL` sets the requested CLI model. `/api/runtime/probe` checks local CLI flags/version without an AI request.
- CLI requests `--sandbox` and `--mode accept-edits` for writers, `plan` for inspectors. Permission requests fail visibly and preserve files; no automatic permission bypass or cross-provider replay. Skill `allowed_tools` remains descriptive; it is not an enforced provider allowlist. Host verification commands run as local subprocesses, so only run trusted projects/checks.
- `AGENT_CLI_FILE_MODE=host-proposals` is the default host writer for non-interactive CLI use. The host supplies bounded source context and the agent returns JSON proposals; the backend rejects unsafe/duplicate/symlink paths, replacement of omitted existing files and a changed workspace before applying files. `direct` opts into provider file tools, which can require interactive approval. Host proposals support complete file replacements/creation, not deletions, and do not enforce a provider tool allowlist.
- `SPRINT_MAX_AGENT_CALLS` defaults to 24 and `SPRINT_TOKEN_BUDGET` to 600000. Token usage records identify provider counts versus estimates. The token budget is a stop threshold checked between invocations, not a hard provider limit; one invocation can exceed it. A budget stop preserves the checkpoint.

### Feature task workflow (opt in per project)

Add to the registered project's `.agent-pm.yml`:

```yaml
workflow:
  feature_tasks: true
preview:
  command: [npm, run, dev, --, --host, 127.0.0.1]
  url: http://127.0.0.1:5173
verification:
  checks:
    - name: order rollback
      command: [python, -m, pytest, tests/test_order_rollback.py, -q]
      kind: test
  acceptance:
    - description: Failure rolls back the bill and stock together
      checks: [order rollback]
  require_acceptance_coverage: true
```

Adjust commands, paths and descriptions to the actual app. Acceptance mappings
match the complete criterion text, not its position. An Architect must provide a
valid dependency graph with task ownership and requirement IDs; missing/cyclic
contracts stop before writing. Feature tasks execute serially and appear separately
in history. Edits outside ownership stop delivery and require inspection/new run.
The original project verification config is captured before agents run; staged
config cannot silently substitute the host checks. Passing mapped checks are
`VERIFIED_BY_CHECK`, not a claim of independent human or production acceptance.
Changing source during/after checks invalidates the evidence.

### Reproducible local evaluation

```bash
PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 python -m app.services.workflow_eval --output /tmp/agent-pm-eval.json
```

This runs deterministic harness regressions in isolated temporary databases with
zero live AI calls. The report retains failures and durations. The 26 natural
language/model benchmark cases remain separately `NOT_RUN`; use
`--require-roadmap-coverage` to block a release until that benchmark is executed.
Current fixture checks do not establish model intelligence or novice usability.

Three SQLite coding fixtures (rollback, duplicate payment, concurrent stock sales)
have persisted-state graders calibrated against broken and reference code.
Model trials are explicitly opt in and use disposable public fixtures:

```bash
PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 python -m app.services.coding_eval --live --model gemini-3.8-flash-medium --file-mode host-proposals --cases E05 --arms single_coder_with_verification --trials 1 --max-calls 3 --token-budget 20000 --timeout 90 --output /tmp/agent-pm-coding-eval.json
```

`--live` uses your CLI credentials/credits and sends fixture code/prompts to the
selected provider. Without it, no AI request is sent. Reports record failed
trials, actual grader outcomes, runtime steps and invocation counts. A single
smoke trial is not a comparison of model quality or proof of all 26 cases.
