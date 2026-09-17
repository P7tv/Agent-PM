"""Validate feature tasks and run a deterministic dependency order.

One staged checkout has exactly one writer at a time. Parallel work requires a
different integration strategy and is deliberately not implied by this graph.
"""
import json
import re
from pathlib import PurePosixPath


def parse_feature_tasks(response, allowed_roles, criteria, supplied=None):
    if supplied is None:
        match = re.search(r'<feature_tasks>\s*(.*?)\s*</feature_tasks>', response, re.S)
        if not match:
            raise ValueError('Feature workflow requires a <feature_tasks> contract')
        supplied = json.loads(match.group(1))
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 12:
        raise ValueError('Feature tasks must be a list of 1–12 tasks')
    tasks = []
    identifiers = set()
    accepted_requirements = {f'AC-{index + 1}' for index in range(len(criteria))}
    for raw in supplied:
        if not isinstance(raw, dict):
            raise ValueError('Invalid feature task')
        identifier = raw.get('id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[\w-]{1,60}', identifier) or identifier in identifiers:
            raise ValueError('Feature task IDs must be unique and bounded')
        identifiers.add(identifier)
        if raw.get('role') not in allowed_roles:
            raise ValueError('Feature task role is outside the selected team')
        if not isinstance(raw.get('title'), str) or not raw['title'].strip():
            raise ValueError('Feature task needs a user-visible title')
        paths = raw.get('owned_paths', [])
        if not isinstance(paths, list) or not paths or any(not isinstance(path, str) or
                PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path for path in paths):
            raise ValueError('Feature ownership must use relative workspace paths')
        dependencies = raw.get('depends_on', [])
        requirements = raw.get('requirements', [])
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise ValueError('Invalid dependencies')
        if not isinstance(requirements, list) or not requirements or not all(isinstance(item, str) and item in accepted_requirements for item in requirements):
            raise ValueError('Tasks must reference known acceptance criteria')
        tasks.append({'id': identifier, 'title': raw['title'][:300], 'role': raw['role'],
                      'description': str(raw.get('description', ''))[:4000],
                      'owned_paths': paths, 'depends_on': dependencies, 'requirements': requirements})
    ordered = []
    remaining = list(tasks)
    done = set()
    while remaining:
        ready = [task for task in remaining if set(task['depends_on']) <= done]
        if not ready:
            raise ValueError('Feature task dependencies are cyclic or reference missing tasks')
        task = ready[0]
        ordered.append(task)
        done.add(task['id'])
        remaining.remove(task)
    if set(requirement for task in ordered for requirement in task['requirements']) != accepted_requirements:
        raise ValueError('Feature task graph leaves acceptance criteria unassigned')
    return ordered


def owns_path(task, relative):
    path = PurePosixPath(relative)
    return any(rule == '.' or path == PurePosixPath(rule) or PurePosixPath(rule) in path.parents
               for rule in task['owned_paths'])
