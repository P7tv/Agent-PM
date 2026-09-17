"""Normalize provider events without publishing raw tool arguments or outputs."""
import json
import time


class AntigravityStream:
    def __init__(self, emit=None):
        self.emit = emit
        self.result = None
        self.conversation_id = None
        self.model = None
        self.failed_tool = None
        self._last_text_at = 0
        self._pending_response = None
        self._seen_steps = set()

    async def flush_response(self):
        if self._pending_response and self.emit:
            await self.emit('RUNTIME_STEP', self._pending_response)
            self._pending_response = None
            self._last_text_at = time.monotonic()

    async def feed(self, line):
        if not line.strip():
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return  # Provider diagnostics are retained in the bounded process tail.
        if not isinstance(event, dict):
            return
        kind = event.get('event')
        if kind == 'init':
            self.model = event.get('init', {}).get('model')
        elif kind == 'result':
            await self.flush_response()
            self.result = event.get('result')
            if isinstance(self.result, dict):
                self.conversation_id = self.result.get('conversation_id') or self.conversation_id
        elif kind == 'step_update':
            step = event.get('step_update', {})
            self.conversation_id = step.get('conversation_id') or self.conversation_id
            tool = step.get('tool_info') or {}
            if step.get('step_type') == 'tool' and step.get('state') == 'ERROR':
                self.failed_tool = str(step.get('tool_name') or tool.get('name') or '')[:160] or None
            if self.emit:
                data = {'step_index': step.get('step_index'), 'state': step.get('state'),
                        'step_type': step.get('step_type'),
                        'conversation_id': self.conversation_id,
                        'tool': str(step.get('tool_name') or tool.get('name') or '')[:160]}
                # Only visible assistant text; no hidden reasoning or raw tool data.
                if step.get('step_type') == 'agent_response':
                    if self._pending_response and self._pending_response['step_index'] != data['step_index']:
                        await self.flush_response()
                    prior = self._pending_response.get('message', '') if self._pending_response else ''
                    data['message'] = (prior + str(step.get('text_delta') or ''))[-2000:]
                    self._pending_response = data
                    if data['state'] == 'DONE' or time.monotonic() - self._last_text_at >= .25:
                        await self.flush_response()
                    return
                else:
                    data['message'] = f"{data['step_type']}: {data['tool'] or data['state']}"
                key = (self.conversation_id, data['step_index'], data['state'], data['tool'])
                if key in self._seen_steps:
                    return
                if len(self._seen_steps) < 10000:
                    self._seen_steps.add(key)
                await self.emit('RUNTIME_STEP', data)

    def final_result(self, process_result):
        if isinstance(self.result, dict):
            return {**process_result, 'stdout': json.dumps(self.result, ensure_ascii=False)}
        # Legacy JSON output remains parseable; incomplete NDJSON is never a success.
        raw = process_result.get('stdout', '').strip()
        try:
            legacy = json.loads(raw)
        except json.JSONDecodeError:
            legacy = None
        if isinstance(legacy, dict) and 'status' in legacy:
            return process_result
        return {**process_result, 'stdout': json.dumps({
            'status': 'ERROR', 'error': 'Runtime ended without a final result; inspect checkpoint before retrying.'})}
