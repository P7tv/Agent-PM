"""Versioned user outcomes and explicit open questions, with conservative defaults."""
import hashlib
import json
import re


def build_product_brief(directive, lead_response, criteria):
    match = re.search(r'<product_brief>\s*(.*?)\s*</product_brief>', lead_response, re.S)
    raw = {}
    if match:
        try:
            candidate = json.loads(match.group(1))
            if isinstance(candidate, dict):
                raw = candidate
        except ValueError:
            pass
    def strings(key):
        values = raw.get(key, [])
        return [item[:2000] for item in values[:20] if isinstance(item, str)] if isinstance(values, list) else []
    questions = []
    for index, item in enumerate(raw.get('questions', [])[:5] if isinstance(raw.get('questions'), list) else []):
        if isinstance(item, dict) and isinstance(item.get('question'), str) and item['question'].strip():
            questions.append({'id': f'Q-{index + 1}', 'question': item['question'][:1000],
                              'blocking': item.get('blocking') is True, 'status': 'OPEN'})
    brief = {'version': 1, 'request': directive,
             'outcome': raw.get('outcome')[:4000] if isinstance(raw.get('outcome'), str) else directive,
             'constraints': strings('constraints'), 'out_of_scope': strings('out_of_scope'),
             'assumptions': strings('assumptions'), 'questions': questions,
             'requirements': [{'id': f'AC-{index + 1}', 'description': description,
                               'verification_status': 'NOT_RUN'} for index, description in enumerate(criteria)]}
    brief['revision'] = hashlib.sha256(json.dumps(brief, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return brief


def task_graph(tasks, implementation_roles, quality_roles):
    # This is the actual serialized checkout execution order. No fictitious
    # parallel writers or file ownership inferred from a role title.
    ordered = [role for role in ('Designer', 'BackendDev') if role in implementation_roles]
    ordered += [role for role in implementation_roles if role not in {'Designer', 'BackendDev', 'FrontendDev', 'DocWriter'}]
    ordered += [role for role in ('FrontendDev', 'DocWriter') if role in implementation_roles]
    ordered += quality_roles
    graph = []
    for role in ordered:
        item = tasks[role]
        graph.append({'id': item.task_id, 'title': item.title, 'role': role,
                      'depends_on': [graph[-1]['id']] if graph else [],
                      'write_policy': 'READ_ONLY' if role in quality_roles else 'SERIAL_STAGED_WRITER'})
    return graph
