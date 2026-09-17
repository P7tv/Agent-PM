"""Bound supporting handoffs consistently before every runtime invocation.

User instructions and acceptance criteria are never truncated. Structured JSON
contracts survive excerpting; oversized mandatory context fails in prompt_builder.
"""
import json
import re


SUPPORTING = {'tech_lead_notes', 'architect_plan', 'backend_specs', 'design_specs',
              'specialist_specs', 'frontend_specs'}


def excerpt(value, limit):
    if len(value) <= limit:
        return value
    contracts = []
    for match in re.finditer(r'<(execution_plan|api_contract|data_contract)>\s*(.*?)\s*</\1>', value, re.S):
        try:
            json.loads(match.group(2))
        except ValueError:
            continue
        contracts.append(match.group(0))
    return (value[:limit] + '\n[Supporting excerpt truncated. Inspect actual repository files. '\
            'Do not infer omitted behavior or successful verification.]\n' + '\n'.join(contracts))


def assemble_task_context(prompt, context):
    safe = dict(context or {})
    for key in SUPPORTING:
        value = safe.get(key)
        if not isinstance(value, str) or not value:
            continue
        try:
            structured = json.loads(value)
        except ValueError:
            structured = None
        if isinstance(structured, (dict, list)):
            continue  # Structured contracts are mandatory, not disposable prose.
        if value in prompt:
            prompt = prompt.replace(value, excerpt(value, 2500))
            safe.pop(key)  # Avoid putting the same evidence in system and task.
    report = safe.get('verification_report')
    if isinstance(report, dict):
        for field in ('stdout', 'stderr'):
            output = report.get(field)
            if isinstance(output, str) and len(output) > 1000:
                prompt = prompt.replace(output, excerpt(output, 1000))
    return prompt, safe
