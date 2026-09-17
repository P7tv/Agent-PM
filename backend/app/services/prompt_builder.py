"""One prompt composition path for consultation, pipeline execution and preview."""
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re


READ_ONLY_MODES = {"consultation", "planning", "design", "verification-analysis", "review"}


def mode_for_role(role):
    normalized = re.sub(r'[^a-z]', '', role.lower())
    if normalized in {'security', 'securityauditor', 'applicationsecurityauditor'}:
        return 'review'
    if normalized in {'systematicdebugger', 'debugger'}:
        return 'verification-analysis'
    return {"TechLead": "planning", "Architect": "planning", "Designer": "design",
            "QATester": "verification-analysis", "Reviewer": "review"}.get(role, "implementation")


def handoff_text(result):
    """Keep contracts intact; never treat model-reported checks as verification."""
    text = result.get("response", "")
    match = re.search(r"<agent_handoff>\s*(.*?)\s*</agent_handoff>", text, re.S)
    if match:
        try:
            data = json.loads(match[1])
            if not isinstance(data, dict) or not isinstance(data.get("summary"), str):
                raise ValueError("Invalid handoff")
            for field in ("changed_files", "risks"):
                if not isinstance(data.get(field, []), list) or not all(isinstance(item, str) for item in data.get(field, [])):
                    raise ValueError(f"Invalid {field}")
            if not isinstance(data.get("contracts", {}), dict) or not isinstance(data.get("checks", []), list):
                raise ValueError("Invalid contracts/checks")
            if not isinstance(data.get("next_owner", ""), str) or not all(
                isinstance(check, dict) and isinstance(check.get("command", ""), str)
                and isinstance(check.get("result", ""), str) for check in data.get("checks", [])
            ):
                raise ValueError("Invalid check entries/next owner")
            data = {key: value for key, value in data.items() if key in {
                "summary", "changed_files", "contracts", "checks", "risks", "next_owner"}}
            data["checks_provenance"] = "agent-reported; use orchestrator verification for pass/fail"
            if "changed_files" in result:
                data["verified_changed_files"] = result["changed_files"]
            return json.dumps(data, ensure_ascii=False)
        except (ValueError, TypeError):
            pass
    return text


@dataclass
class PromptBundle:
    system: str
    active_skills: list
    trace: dict


def build_prompt(manager, role, workspace, context=None, agent=None, intent="", mode=None):
    mode = mode or mode_for_role(role)
    if mode not in READ_ONLY_MODES | {"implementation"}:
        raise ValueError("Invalid execution mode")
    budget = max(12000, min(200000, int(os.environ.get("AGENT_PROMPT_MAX_CHARS", "48000"))))
    root = Path(workspace).resolve()
    warnings, trimmed, sources = [], [], []

    def bounded(text, limit, label):
        if len(text) <= limit:
            return text
        trimmed.append(label)
        return text[:max(0, limit - 100)] + "\n[Context excerpt truncated; inspect the cited source before relying on omitted details.]"

    def source(path, kind, text):
        sources.append({"kind": kind, "path": str(path),
                        "sha256": hashlib.sha256(text.encode()).hexdigest()})

    core = manager.get_base_role_skill(role)
    if core.file_path:
        source(core.file_path, "core", core.raw_content)
    core = replace(core, instructions=bounded(core.instructions, 7000, "core"))
    project = manager.get_project_role_skill(role, workspace)
    if project:
        if len(project.instructions) > 6000:
            raise ValueError("Project role rules exceed 6000 characters; move detailed methodology into operational skill references")
        source(project.file_path, "project-role", project.raw_content)
    selection_mode = getattr(agent, "skill_mode", "AUTO") if agent else "AUTO"
    selected = []
    reasons = {}
    if selection_mode == "MANUAL":
        for name in getattr(agent, "equipped_skills", []) or []:
            try:
                skill = manager.get_skill(name, workspace, required=True)
                selected.append(skill)
                reasons[skill.name] = "manual selection"
            except ValueError as error:
                warnings.append(str(error))
    elif intent.strip() and not re.fullmatch(r"(?:hello|hi|hey|thanks|thank you|สวัสดี(?:ครับ|ค่ะ)?|ขอบคุณ(?:ครับ|ค่ะ)?)[.!\s]*", intent.strip(), re.I):
        for name in getattr(agent, 'equipped_skills', []) or []:
            try:
                skill = manager.get_skill(name, workspace, required=True)
                selected.append(skill)
                reasons[skill.name] = 'pinned skill; AUTO remains enabled'
            except ValueError as error:
                warnings.append(str(error))
        matching_context = {}
        for key in ('stack_type', 'frameworks', 'test_runner', 'purpose_summary', 'acceptance_criteria'):
            if context and context.get(key):
                matching_context[key] = context[key]
        match_intent = intent + '\n' + json.dumps(matching_context, ensure_ascii=False)[:4000]
        excluded_paths = {core.file_path, project.file_path if project else None, *[s.file_path for s in selected]}
        auto_limit = max(1, min(6, int(os.environ.get('AGENT_AUTO_MAX_SKILLS', '4'))))
        pinned_count = len({s.file_path for s in selected if s.file_path not in {core.file_path, project.file_path if project else None}})
        automatic = manager.match_skills_for_task(role, match_intent, workspace,
            max_skills=max(0, auto_limit - pinned_count), excluded_paths=excluded_paths,
            excluded_names=set(manager.ROLE_ALIAS_MAP.values()) - {'security-auditor', 'systematic-debugger'})
        selected.extend(automatic)
        reasons.update({skill.name: 'AUTO task/context match (Thai/English); excludes loaded core role' for skill in automatic})
    excluded = {core.file_path, project.file_path if project else None}
    active = []
    for skill in selected:
        if skill.file_path in excluded:
            continue
        excluded.add(skill.file_path)
        source(skill.file_path, "operational-skill", skill.raw_content)
        active.append(replace(skill, instructions=bounded(skill.instructions, max(800, 8000 // max(1, len(selected))), skill.name)))

    # Criteria are mandatory; other prior-agent output is bounded evidence.
    original_context = dict(context or {})
    evidence_keys = {"tech_lead_notes", "architect_plan", "backend_specs", "design_specs", "specialist_specs", "frontend_specs"}
    safe_context = {}
    for key, value in original_context.items():
        if key in evidence_keys:
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            if text and text in intent:
                continue
            try:
                structured = json.loads(text)
            except (ValueError, TypeError):
                structured = None
            if isinstance(structured, dict):
                # Do not silently remove API/schema fields from a structured contract.
                safe_context[key] = text
            else:
                safe_context[key] = bounded(text, 2500, key)
        elif key == "project_memories":
            safe_context[key] = bounded(str(value), 2000, key)
        elif key == "verification_report" and isinstance(value, dict):
            def report_excerpt(item):
                if isinstance(item, dict):
                    return {name: bounded(str(entry), 1000, f"verification:{name}") if name in {"stdout", "stderr"}
                            else report_excerpt(entry) for name, entry in item.items()}
                if isinstance(item, list):
                    return [report_excerpt(entry) for entry in item]
                return item
            safe_context[key] = report_excerpt(value)
        else:
            safe_context[key] = value
    persona = getattr(agent, "persona", "") or ""
    system = manager.synthesize_agent_prompt(role, safe_context, workspace, core, active,
        persona=persona, execution_mode=mode, project_rule_skill=project)

    system_file = Path(__file__).resolve().parents[2] / "agents" / "SYSTEM.md"
    if system_file.is_file():
        text = system_file.read_text(encoding="utf-8")
        source(system_file, "system", text)
        system = text + "\n\n" + system
    # Root rules are loaded explicitly for both backends. Nested rules stay scoped.
    rules = root / "AGENTS.md"
    if rules.is_file() and rules.resolve().is_relative_to(root):
        with rules.open(encoding="utf-8") as handle:
            text = handle.read(6001)
        if len(text) > 6000:
            raise ValueError("Project AGENTS.md exceeds 6000 characters; shorten root rules and move detail into scoped references")
        source(rules, "project-rules", text)
        system += f"\nPROJECT AGENTS.md RULES ({rules}):\n{text}\nBefore editing a nested directory, inspect its scoped AGENTS.md rules."

    # Markdown references are data; scripts are never executed by the loader.
    reference_count = 0
    for skill in ([project] if project else []) + active:
        skill_root = Path(skill.file_path).resolve().parent
        for target in re.findall(r"\[[^\]]*\]\(([^\s)#]+)(?:#[^)]*)?\)", skill.instructions):
            if "://" in target or not target.lower().endswith(".md"):
                continue
            path = (skill_root / target).resolve()
            if not path.is_relative_to(skill_root) or not path.is_file():
                warnings.append(f"Missing or out-of-scope reference: {skill.name}/{target}")
                continue
            if reference_count >= 3:
                trimmed.append(f"reference:{skill.name}/{target}")
                continue
            with path.open(encoding="utf-8", errors="replace") as handle:
                text = handle.read(512 * 1024 + 1)
            if len(text.encode("utf-8")) > 512 * 1024:
                warnings.append(f"Oversized reference: {skill.name}/{target}")
                continue
            source(path, "skill-reference", text)
            system += f"\nREFERENCE DATA ({path}):\n{bounded(text, 1500, target)}"
            reference_count += 1
    warnings.extend(f"{path}: {message}" for path, message in list(manager.diagnostics.items())[:20])
    # Mode rules remain last even after project Markdown/reference loading.
    system += f"\nWorkspace boundary: operate only inside {root}.\nFinal reminder: execution-mode limits override reference workflows. Report only checks actually performed, distinguish verified facts from assumptions, and follow the current user scope."
    if len(system) > budget:
        raise ValueError(f"Required prompt context exceeds {budget} characters; shorten criteria or project rules")
    trace = {"role": role, "execution_mode": mode, "skill_mode": selection_mode,
        "persona_source": getattr(agent, "persona_source", "explicit") if agent else "role",
        "sources": sources, "selected_skills": [skill.name for skill in selected],
        "operational_skills": [skill.name for skill in active], "selection_reasons": reasons,
        "warnings": list(dict.fromkeys(warnings)), "truncated_sections": list(dict.fromkeys(trimmed)),
        "context_sections": sorted(safe_context), "characters": len(system), "max_characters": budget,
        "tool_policy": "execution mode; skill allowed_tools are advisory metadata, not runtime permissions",
        "sha256": hashlib.sha256(system.encode()).hexdigest()}
    return PromptBundle(system, active, trace)
