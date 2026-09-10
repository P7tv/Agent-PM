# Base Role Playbooks and Adaptive Multi-Skill System Design Specification

## 1. Executive Summary & Problem Statement

In previous iterations of the Virtual AI Office PM Dashboard, assigning a skill from the Skill Store (`SkillStoreModal`) performed a destructive overwrite of the agent's primary identity (e.g. assigning `test-driven-development` to `TechLead` changed their core role skill, stripping away their leadership and orchestration prompts).

This specification establishes a **Two-Tier Architecture**:
1. **Tier 1: Core Role Foundation (Base System Prompt)** — Permanent, immutable core identity for each agent (`TechLead`, `Architect`, `FrontendDev`, `BackendDev`, `QATester`) defining baseline responsibilities, boundary limits, and behavior.
2. **Tier 2: Multi-Skill Capabilities (Dynamic Store Library)** — A modular library of specialized engineering skills (`test-driven-development`, `systematic-debugging`, `ui-styling`, `design`, `verification-before-completion`, etc.) that agents can equip simultaneously (Multi-Skills) or dynamically leverage on-demand.

Additionally, the system adopts a **"Zero-Config Auto by Default + Pro Manual Override"** paradigm:
- **Auto-Adaptive Mode (Default)**: Agents automatically leverage relevant domain skills from the library when tackling complex engineering tasks without requiring manual PM setup.
- **Manual Control**: The PM can equip, add, or remove multiple skills per agent in the UI.
- **On-Demand Rule**: For casual chat, questions, or greetings, agents respond directly without bloated skill overhead.

---

## 2. Architecture & Data Model

```
+-------------------------------------------------------------------------------+
|                             AI Agent Roster                                   |
|  (TechLead, Architect, FrontendDev, BackendDev, QATester)                     |
+-------------------------------------------------------------------------------+
                                      |
       +------------------------------+------------------------------+
       |                                                             |
       v                                                             v
+------------------------------------+             +------------------------------------+
| Tier 1: Base Role Playbook         |             | Tier 2: Multi-Skill Capabilities   |
| (Permanent Core System Prompt)     |             | (Equipped & Auto-Adaptive Store)   |
|                                    |             |                                    |
| - Defined in `backend/skills/<role>`|             | - Equipped: ["ui-styling", "tdd"]  |
| - Never overwritten                |             | - Auto fallback: Role Domain Tags  |
| - Dictates domain boundaries       |             | - Triggers: Only when complex/req  |
+------------------------------------+             +------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                       Unified Prompt Synthesizer                              |
|   [Core Role Playbook] + [Equipped/Relevant Skills] + [Project Context]       |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                     Antigravity CLI (Headless agy -p)                         |
|   --add-dir <workspace> --dangerously-skip-permissions --effort low           |
+-------------------------------------------------------------------------------+
```

### 2.1 Database Schema Migrations (`state.db`)

In SQLite table `agent_states`:
```sql
ALTER TABLE agent_states ADD COLUMN equipped_skills_json TEXT DEFAULT '[]';
ALTER TABLE agent_states ADD COLUMN skill_mode TEXT DEFAULT 'AUTO'; -- 'AUTO' or 'MANUAL'
```

- `role`: Primary key together with `project_id`.
- `skill_name`: Maintained for backward compatibility (holds primary or active skill).
- `equipped_skills_json`: JSON list of skill names equipped on this agent, e.g. `["ui-styling", "test-driven-development"]`.
- `skill_mode`: `'AUTO'` (agent dynamically activates domain skills) or `'MANUAL'` (strictly uses equipped skills).

### 2.2 Skill Library Domain Taxonomy

Each skill in `~/.gemini/config/skills` and `backend/skills` is cataloged with domain tags:
- **Frontend Domain (`frontend`)**: `ui-styling`, `design`, `brand`, `ui-ux-pro-max`
- **Backend Domain (`backend`)**: `database`, `api-design`, `systematic-debugging`
- **Quality & Testing (`qa`)**: `test-driven-development`, `verification-before-completion`, `systematic-debugging`
- **Architecture & Lead (`lead`)**: `system-architecture`, `brainstorming`, `writing-plans`, `requesting-code-review`, `receiving-code-review`
- **General Engineering (`general`)**: `using-git-worktrees`, `executing-plans`, `subagent-driven-development`

---

## 3. Execution Flow & Prompt Synthesis

### 3.1 Prompt Composition

When dispatching a task or console message to an agent:
```python
# 1. Base Role Playbook (100% permanent)
base_role_skill = skill_manager.get_base_role_skill(role)

# 2. Equipped or Auto Domain Skills
if agent_state.skill_mode == "MANUAL" and agent_state.equipped_skills:
    active_skills = [skill_manager.get_skill(s) for s in agent_state.equipped_skills]
else:
    # Auto-Adaptive: candidate domain skills for this role
    active_skills = skill_manager.get_domain_skills_for_role(role)

# 3. On-Demand Activation Directives
prompt = f"""
{base_role_skill.instructions}

============================================================
🎯 SKILL CAPABILITIES CATALOG FOR {role.upper()}
============================================================
{format_skills_catalog(active_skills)}

SKILL ACTIVATION RULES:
1. CASUAL / SIMPLE: For greetings, short questions, status inquiries, or straightforward answers, respond directly and concisely. DO NOT execute complex multi-step skill checklists.
2. ENGINEERING TASKS: When the user requests coding, bug investigation, testing, or architectural design matching one of your skills, adopt that skill's methodology.
3. TRANSPARENCY: If you utilize a specific skill in your work, note it with `[Used Skill: <skill-name>]` in your response.

============================================================
🔍 WORKSPACE CONTEXT: {workspace_path}
============================================================
{project_context_summary}
"""
```

### 3.2 Antigravity CLI Invocations

All CLI executions continue using Google Account authenticated `agy`:
```bash
agy --add-dir <workspace_path> -p <full_prompt> --dangerously-skip-permissions --effort low
```

---

## 4. API Endpoints

### 4.1 `GET /api/projects/{project_id}/agents/{role}/skills`
Returns full skill profile for the agent:
```json
{
  "role": "FrontendDev",
  "base_role_playbook": {
    "name": "frontend-dev",
    "title": "Frontend UI & Client Experience Engineer",
    "instructions": "# Frontend Developer Playbook..."
  },
  "skill_mode": "AUTO",
  "equipped_skills": ["ui-styling", "test-driven-development"],
  "available_skills": [ ...list of all store skills with domain and equipped flags... ]
}
```

### 4.2 `POST /api/projects/{project_id}/agents/{role}/skills/add`
Request body: `{"skill_name": "ui-styling"}`
Adds skill to `equipped_skills_json` and updates `skill_mode` to `'MANUAL'`.

### 4.3 `POST /api/projects/{project_id}/agents/{role}/skills/remove`
Request body: `{"skill_name": "ui-styling"}`
Removes skill from `equipped_skills_json`. If empty, reverts `skill_mode` to `'AUTO'`.

### 4.4 `POST /api/projects/{project_id}/agents/{role}/skills/set-mode`
Request body: `{"mode": "AUTO" | "MANUAL"}`
Switches between Auto-Adaptive and Manual Equipped modes.

---

## 5. Frontend UI / UX Specifications

### 5.1 Playbooks & Skills Tab (`FocusRoomView.jsx`)
- **Left Panel**: Agent Specialists roster list.
- **Top Section (Core Role)**:
  - Displays **"Core Role Playbook"** with badge `CORE ROLE`.
  - Read/Edit markdown viewer for base role instructions.
- **Equipped Skills Section**:
  - Displays chip badges for all currently equipped skills:
    `[ 🎨 UI Styling (AGY) ✕ ]` `[ 🧪 Test Driven Development ✕ ]`
  - Toggle button: `[ Mode: Auto-Adaptive 🔄 ]` vs `[ Mode: Manual ⚙️ ]`
  - Button: `+ Add Skill from Store`

### 5.2 Skill Store Modal (`SkillStoreModal.jsx`)
- Browses 31+ Antigravity skills.
- Replaces legacy destructive `Assign to...` with:
  - **"+ Equip to Agent"** dropdown or checkboxes.
  - Indicator tags showing which agents currently equip this skill (e.g. `[Equipped: FrontendDev, QATester]`).
  - Allows one-click adding/removing per agent.

### 5.3 Team Console (`FocusRoomView.jsx`)
- Parses `[Used Skill: <name>]` from agent response text.
- Displays a clean visual badge: `⚡ Used Skill: <name>` above the agent message bubble.

---

## 6. Testing & Verification Plan

1. **Unit Tests**:
   - `test_base_role_never_overwritten`: Ensure adding skills never changes the base playbook.
   - `test_multi_skills_persistence`: Store multiple skills in SQLite and retrieve accurately.
   - `test_skill_domain_matching`: Ensure `FrontendDev` gets UI skills in Auto mode, `BackendDev` gets backend skills.
   - `test_on_demand_simple_vs_complex`: Ensure simple greetings don't trigger heavy skill prompt overhead.
2. **API Endpoint Tests**:
   - Verify `GET`, `POST add`, `POST remove`, `POST set-mode`.
3. **End-to-End UI Validation**:
   - Build frontend bundle with `npm run build`.
   - Verify in browser: Add multiple skills to FrontendDev, test chat in Console, observe skill tags.
