# Architecture Spec: AGY Skills Sync & Online Skill Downloader

**Date**: 2026-09-10  
**Status**: Approved  
**Author**: AI PM Architect & Antigravity  

---

## 1. Overview & Objective

The objective of this subsystem is to seamlessly connect My PM's agent orchestration runtime with:
1. **Local Antigravity (`agy`) Skills** installed at `~/.gemini/config/skills/` (over 22 high-grade engineering skills like `test-driven-development`, `systematic-debugging`, `ui-ux-pro-max`, `super-video-maker`, `design-system`).
2. **Online Community / GitHub Skill Repositories**, allowing users to download, inspect, sanitize, and bind remote markdown playbooks directly into their project or global stock inventory.

---

## 2. Architecture & Tier Hierarchy

The `SkillManager` service resolves skills according to a 4-tier precedence hierarchy:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Project-Local Override (tier: "project")                │
│    Path: <project_path>/.agents/skills/<skill_name>/SKILL.md │
├─────────────────────────────────────────────────────────────┤
│ 2. AGY Installed Skills (tier: "agy")                       │
│    Path: ~/.gemini/config/skills/<skill_name>/SKILL.md      │
│    Auto-scanned live; immediately available without reboot  │
├─────────────────────────────────────────────────────────────┤
│ 3. Global Stock Skills (tier: "stock")                      │
│    Path: backend/skills/<skill_name>/SKILL.md               │
│    Curated standard roles (Tech Lead, QA, DevOps, etc.)     │
├─────────────────────────────────────────────────────────────┤
│ 4. Built-in Fallback (tier: "fallback")                     │
│    Safe core engineering prompt generated in memory         │
└─────────────────────────────────────────────────────────────┘
```

### Dynamic Role-to-Skill Binding
Agents can now be bound to *any* installed or downloaded skill:
- An agent `QATester` can have its primary skill swapped to `test-driven-development` (from `agy`).
- An agent `Debugger` can be bound to `systematic-debugging` (from `agy`).
- An agent `FrontendDev` can be bound to `ui-ux-pro-max` (from `agy`).
- The binding is stored in the database (`agent_states.skill_name`, `agent_states.skill_tier`, `agent_states.skill_title`).

---

## 3. Online GitHub & Web URL Downloader

### 3.1 Supported URL Patterns
- **Direct Raw Markdown**:
  `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/path/to/SKILL.md`
- **GitHub Blob URL**:
  `https://github.com/<owner>/<repo>/blob/<branch>/path/to/SKILL.md` (automatically converted to raw URL)
- **Generic HTTPS Raw URLs**:
  Any accessible HTTPS endpoint returning plain text / markdown.

### 3.2 Security & Verification Guardrails
To prevent Prompt Injection and Denial of Service:
1. **Size Limit**: Maximum 512 KB per skill file.
2. **Format Validation**: Must be valid UTF-8 and contain standard markdown structure. If YAML frontmatter is present, it is parsed and validated.
3. **Harmful Pattern Heuristics**: Rejects files containing explicit dangerous instructions aimed at bypassing safe agent isolation or leaking environment secrets.
4. **Target Isolation**:
   - `project`: Written to `<project_path>/.agents/skills/<skill_name>/SKILL.md`.
   - `stock`: Written to `backend/skills/<skill_name>/SKILL.md`.

---

## 4. REST API Contracts

### 4.1 `GET /api/skills`
Returns the full catalogue of available skills across all accessible sources.
```json
[
  {
    "name": "test-driven-development",
    "title": "Test-Driven Development",
    "description": "Use when implementing any feature or bugfix, before writing implementation code",
    "tier": "agy",
    "allowed_tools": ["bash", "view_file", "write_file", "edit_file"],
    "file_path": "/Users/panpan/.gemini/config/skills/test-driven-development/SKILL.md"
  },
  {
    "name": "backend-dev",
    "title": "Backend API & Core Systems Engineer",
    "description": "Specialist in server-side architecture...",
    "tier": "stock",
    "allowed_tools": ["bash", "view_file", "write_file", "edit_file"]
  }
]
```

### 4.2 `POST /api/skills/download`
Downloads and installs an online skill.
**Request**:
```json
{
  "url": "https://raw.githubusercontent.com/owner/repo/main/skills/custom-agent/SKILL.md",
  "name": "custom-agent",
  "target": "project",
  "project_id": "f1"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Skill 'custom-agent' installed successfully.",
  "skill": {
    "name": "custom-agent",
    "title": "Custom Agent",
    "tier": "project"
  }
}
```

### 4.3 `POST /api/projects/{project_id}/agents/{role}/assign-skill`
Assigns any available skill (stock, agy, project) to a specific agent in the project.
**Request**:
```json
{
  "skill_name": "test-driven-development"
}
```
**Response**:
```json
{
  "status": "success",
  "project_id": "f1",
  "role": "QATester",
  "new_skill": "test-driven-development",
  "tier": "agy"
}
```

---

## 5. Frontend UI/UX Integration

### 5.1 "Playbooks & Skills" Tab Upgrades
1. **Source Tier Badges**:
   - 🟢 `AGY` pill for skills synchronized from Antigravity.
   - 🔵 `Stock` pill for internal baseline skills.
   - 🟣 `Project` pill for workspace overrides.
2. **Action Header Buttons**:
   - `[+ Install / Sync Skills]` button next to the team roster.
3. **Skill Store & Downloader Modal**:
   - **Tab 1: AGY Skills Browser**: Grid/List of installed `~/.gemini/config/skills/` with search bar and 1-click `[Assign to Agent]` dropdown.
   - **Tab 2: Online Downloader**: URL input with validation feedback, preview drawer, and `[Download & Apply]` button.
4. **Live Playbook Assignment**:
   - Dropdown selector on the right panel allowing instantaneous reassignment of an agent's active playbook.

---

## 6. Testing & Verification Strategy

1. **Unit Tests (`test_skill_manager_sync.py`)**:
   - Test scanning of AGY config directory.
   - Test tier resolution priority (project > agy > stock > fallback).
   - Test online downloader URL conversion and file writing.
   - Test validation of dangerous/malformed markdown payloads.
2. **API Tests (`test_skill_download_routes.py`)**:
   - Test `POST /api/skills/download`.
   - Test `POST /api/projects/{id}/agents/{role}/assign-skill`.
   - Test `GET /api/skills` returns combined tiers.
3. **End-to-End Browser Verification**:
   - Open Focus Room -> Playbooks & Skills.
   - Click "Install / Sync Skills".
   - Browse AGY skills (e.g. `test-driven-development`), assign to `QATester`.
   - Verify agent card and playbook preview updates live.
