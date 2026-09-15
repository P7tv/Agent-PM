"""Deterministic contracts shared by the sprint planner and quality gates."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List


STANDARD_IMPLEMENTERS = {"Designer", "FrontendDev", "BackendDev", "DocWriter"}
ALWAYS_REQUIRED = ("QATester", "Reviewer")


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_.+-]*", (value or "").lower()))


def _extract_json_block(text: str, tag: str) -> Dict[str, Any] | None:
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text or "", re.I | re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def build_execution_plan(
    directive: str,
    architect_response: str,
    metadata: Dict[str, Any] | None,
    custom_agents: Iterable[Any] = (),
) -> Dict[str, Any]:
    """Choose only the roles relevant to this directive.

    An Architect can provide a strict ``<execution_plan>`` JSON contract. A
    deterministic inference is used when that contract is absent or invalid.
    """
    metadata = metadata or {}
    custom_agents = list(custom_agents)
    allowed = STANDARD_IMPLEMENTERS | {getattr(a, "role", "") for a in custom_agents}
    structured = _extract_json_block(architect_response, "execution_plan")
    roles: List[str] = []
    criteria: List[str] = []

    if structured:
        raw_roles = structured.get("roles", [])
        if isinstance(raw_roles, list):
            roles = [role for role in raw_roles if isinstance(role, str) and role in allowed]
        raw_criteria = structured.get("acceptance_criteria", [])
        if isinstance(raw_criteria, list):
            criteria = [str(item).strip() for item in raw_criteria if str(item).strip()][:12]

    if not roles:
        text = " ".join(
            [directive, str(metadata.get("stack_type", "")), str(metadata.get("purpose_summary", ""))]
            + [str(x) for x in metadata.get("frameworks", [])]
        ).lower()
        thai_frontend = any(word in text for word in ("หน้าจอ", "หน้าเว็บ", "ปุ่ม", "ฟอร์ม", "การแสดงผล", "ดีไซน์"))
        thai_backend = any(word in text for word in ("หลังบ้าน", "เอพีไอ", "ฐานข้อมูล", "เซิร์ฟเวอร์", "ยืนยันตัวตน"))
        thai_build = any(word in directive.lower() for word in ("สร้าง", "เพิ่มฟีเจอร์", "ทำระบบ", "พัฒนา"))
        thai_docs = any(word in text for word in ("คู่มือ", "เอกสาร"))
        doc_only = (bool(re.search(r"\b(readme|documentation|docs?)\b", text)) or thai_docs) and not bool(
            re.search(r"\b(build|implement|feature|api|page|component|bug|fix|สร้าง|เพิ่ม|แก้)\b", text)
        )
        frontend = thai_frontend or bool(re.search(
            r"\b(frontend|ui|ux|page|screen|component|react|vue|vite|css|html|dashboard|landing|button|form|หน้า|หน้าจอ)\b",
            text,
        ))
        backend = thai_backend or bool(re.search(
            r"\b(backend|api|endpoint|database|sql|server|fastapi|django|flask|auth|webhook|queue|worker|schema|migration|ฐานข้อมูล)\b",
            text,
        ))
        broad = thai_build or bool(re.search(
            r"\b(fullstack|feature|application|app|system|multiplayer|build|implement|สร้างระบบ|ฟีเจอร์)\b",
            directive.lower(),
        ))
        doc_relevant = thai_docs or bool(re.search(r"\b(readme|documentation|docs?|public api|setup)\b", text))

        if doc_only:
            roles.append("DocWriter")
        else:
            if broad and not frontend and not backend:
                stack = text
                frontend = any(x in stack for x in ("react", "vue", "svelte", "frontend", "node.js"))
                backend = any(x in stack for x in ("python", "fastapi", "django", "flask", "express", "backend", "go", "rust"))
                if not frontend and not backend:
                    frontend = backend = True
            if frontend:
                roles.extend(["Designer", "FrontendDev"])
            if backend:
                roles.append("BackendDev")
            if doc_relevant:
                roles.append("DocWriter")
            if not roles:
                stack = text
                roles.append("FrontendDev" if any(x in stack for x in ("react", "vue", "svelte")) else "BackendDev")

        for agent in custom_agents:
            role = getattr(agent, "role", "")
            descriptor = " ".join(
                str(getattr(agent, key, "") or "") for key in ("role", "title", "thought", "skill_title", "skill_name")
            )
            descriptor_lower = descriptor.lower()
            intent_words = _words(directive) - {
                "build", "create", "implement", "add", "fix", "repair", "update",
                "feature", "system", "app", "project", "สร้าง", "เพิ่ม", "แก้", "ทำ",
            }
            overlap = intent_words & _words(descriptor)
            domain_affinity = any(
                any(trigger in text for trigger in triggers) and any(skill in descriptor_lower for skill in skills)
                for triggers, skills in (
                    (("game", "multiplayer", "vehicle", "3d"), ("three", "webgl", "shader", "render", "game")),
                    (("payment", "checkout", "billing", "stripe"), ("payment", "stripe", "billing")),
                    (("model", "training", "data", "machine learning"), ("ml", "data", "model", "pytorch")),
                    (("deploy", "docker", "cloud", "ci"), ("devops", "cloud", "docker", "infrastructure")),
                    (("security", "auth", "permission"), ("security", "auth", "identity")),
                )
            )
            if role and (overlap or domain_affinity):
                roles.append(role)

    # Stable de-duplication keeps dependencies predictable.
    roles = list(dict.fromkeys(role for role in roles if role in allowed))
    if "FrontendDev" in roles and "Designer" in roles:
        roles.remove("Designer")
        roles.insert(0, "Designer")
    if not criteria:
        criteria = [
            f"The requested behavior is implemented: {directive}",
            "Existing supported checks remain green",
            "Changed files and verification results are reported",
        ]
    return {"roles": roles, "quality_roles": list(ALWAYS_REQUIRED), "acceptance_criteria": criteria}


def parse_reviewer_verdict(text: str) -> Dict[str, Any]:
    """Parse a reviewer response. Missing contracts fail closed."""
    raw = _extract_json_block(text, "review_verdict")
    if raw:
        verdict = str(raw.get("verdict", "")).upper()
        if verdict in {"APPROVED", "CHANGES_REQUESTED", "BLOCKED"}:
            findings = raw.get("findings", [])
            owners = raw.get("owners", [])
            return {
                "verdict": verdict,
                "findings": findings if isinstance(findings, list) else [str(findings)],
                "owners": owners if isinstance(owners, list) else [str(owners)],
            }
    match = re.search(r"^\s*VERDICT\s*:\s*(APPROVED|CHANGES_REQUESTED|BLOCKED)\s*$", text or "", re.I | re.M)
    if match:
        return {"verdict": match.group(1).upper(), "findings": [], "owners": []}
    return {
        "verdict": "BLOCKED",
        "findings": ["Reviewer did not return the required structured verdict."],
        "owners": [],
    }


def choose_fix_owner(report: str, available_roles: Iterable[str]) -> str:
    """Route a failure using file paths first, then domain language."""
    available = set(available_roles)
    paths = re.findall(r"(?:^|\s)([\w./-]+\.(?:tsx?|jsx?|css|html|py|go|rs|sql))(?::\d+)?", report or "", re.I)
    frontend_path = any(re.search(r"(?:frontend|client|web|src/components|src/pages)|\.(?:tsx?|jsx?|css|html)$", p, re.I) for p in paths)
    backend_path = any(re.search(r"(?:backend|server|api|routes?|models?)|\.(?:py|go|rs|sql)$", p, re.I) for p in paths)
    if frontend_path and "FrontendDev" in available:
        return "FrontendDev"
    if backend_path and "BackendDev" in available:
        return "BackendDev"
    lower = (report or "").lower()
    if "FrontendDev" in available and re.search(r"\b(ui|css|component|browser|dom|frontend|jsx|tsx)\b", lower):
        return "FrontendDev"
    if "BackendDev" in available:
        return "BackendDev"
    if "FrontendDev" in available:
        return "FrontendDev"
    return next(iter(available), "BackendDev")
